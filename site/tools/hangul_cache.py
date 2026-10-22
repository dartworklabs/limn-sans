"""Disposable, exact-input Hangul build records; no cached bytes are executable.

The producer owns the inputs and successful glyphs. This module owns bounded JSON,
content identities, atomic publication and POSIX per-key locks (macOS and Linux).
"""

import fcntl
import hashlib
import json
import math
import os
import platform
import re
import stat
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from pathlib import Path

__all__ = [
    "GlyphCache",
    "GlyphRecord",
    "Miss",
    "cache_enabled",
    "fingerprint",
    "identity",
    "read_json",
    "atomic_json",
    "key_lock",
]

MAX_BYTES = 2 * 1024 * 1024
SCHEMA = 1
_RULE_ENV = {
    "LIMN_KO_STEMS",
    "LIMN_KO_SMOOTH",
    "LIMN_KO_CONTRAST",
    "LIMN_RIM_CLAMP",
    "LIMN_STEM_K2",
    "LIMN_STEM_B1",
    "LIMN_XH_OUT",
    "LIMN_WCURVE",
    "LIMN_WSTEMS",
    "LIMN_S900",
    "LIMN_COUNTER_KEEP_SMALL",
}
_CODE = ("hangul.py", "build_hangul.py", "audit_hangul.py", "weights.py", "ofl_header.py", "hangul_cache.py")


def cache_enabled() -> bool:
    """Read the shared switch for both glyph records and the smoothing disk cache."""
    return os.environ.get("LIMN_KO_CACHE", "1") != "0"


def identity(value: object) -> str:
    """Hash finite JSON inputs canonically; sequence order remains significant."""
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _file_hash(path: Path) -> str:
    """Hash actual file bytes without retaining large font or native-library buffers."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _dependencies() -> dict:
    """Fingerprint installed Python/native producer code, including same-version local edits."""
    import shapely

    distributions = {}
    for name in ("fonttools", "skia-pathops", "numpy", "scipy", "shapely"):
        dist = metadata.distribution(name)
        files = {}
        for entry in sorted(dist.files or (), key=str):
            if Path(str(entry)).suffix in {".py", ".pyd", ".dll", ".dylib"} or ".so" in Path(str(entry)).name:
                files[str(entry)] = _file_hash(Path(str(dist.locate_file(entry))))
        if not files:
            raise RuntimeError(f"cannot fingerprint installed producer dependency: {name}")
        distributions[name] = {"version": dist.version, "files": identity(files)}
    return {
        "python": sys.version,
        "implementation": sys.implementation.name,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "geos": shapely.geos_version_string,
        "distributions": distributions,
    }


def fingerprint(tools: Path, *, latin: bool = True, refresh_dependencies: bool = False) -> dict:
    """Capture actual producers, parents, effective environment and optional Latin source.

    Missing parents fail the build. Missing Latin is an explicit input state: syllable-only
    probes can run before make play; unit symbols still fail in their existing producer.
    Call once after inputs are ready; sources must remain frozen during a build.
    """
    if refresh_dependencies:
        _dependencies.cache_clear()
    files = {name: _file_hash(tools / name) for name in _CODE}
    for master in ("L", "R", "B", "EB"):
        name = f"hangul/NanumSquareRound{master}.ttf"
        files[name] = _file_hash(tools / name)
    if latin:
        path = tools.parent / "limn-font-play.js"
        files["limn-font-play.js"] = _file_hash(path) if path.exists() else "missing"
    return {
        "files": files,
        "dependencies": _dependencies(),
        "environment": {k: v for k, v in os.environ.items() if k in _RULE_ENV},
    }


def _pairs(items):
    """Reject ambiguous duplicate JSON keys before records reach a producer."""
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _bounded_depth(raw: bytes) -> bool:
    """Reject excessive JSON nesting before the standard parser can recurse."""
    depth, string, escaped = 0, False, False
    for byte in raw:
        if string:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                string = False
        elif byte == 34:
            string = True
        elif byte in (91, 123):
            depth += 1
            if depth > 24:
                return False
        elif byte in (93, 125):
            depth -= 1
    return True


def read_json(path: Path):
    """Read a small regular non-symlink JSON file; malformed/local I/O failures are misses."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                return None
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES or not _bounded_depth(raw):
            return None
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant, parse_float=_finite_float)
        _check_unicode(value)
        return value
    except (OSError, ValueError, RecursionError):
        return None


def _reject_constant(value):
    """Reject JSON extensions such as NaN rather than handing non-finite values downstream."""
    raise ValueError(f"non-finite JSON constant: {value}")


def _finite_float(value):
    """Reject overflowing JSON exponents before canonical hashing or numeric use."""
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite JSON number")
    return result


def _check_unicode(value) -> None:
    """Reject unpaired surrogates in all cached keys/values, including unrelated old records."""
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_unicode(key)
            _check_unicode(item)
    elif isinstance(value, list):
        for item in value:
            _check_unicode(item)


def atomic_json(path: Path, value: object) -> None:
    """Publish complete bounded JSON via same-directory replace; failures propagate to the caller."""
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("cache record exceeds byte limit")
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def key_lock(path: Path):
    """Serialize same-key publishers; kernel releases the retained lock file after interruption."""
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "r+b") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise OSError("cache lock must be a regular file")
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


@dataclass(frozen=True)
class Miss:
    """No usable record exists; the producer must recompute this glyph family."""


@dataclass(frozen=True)
class GlyphRecord:
    """All accepted weights of one character, plus the original ordered held adjustments."""

    glyphs: dict
    held: list


def _number(value) -> bool:
    """Recognize finite JSON numbers while excluding booleans."""
    return type(value) in (int, float) and math.isfinite(value)


def _outline(value) -> bool:
    """Recognize the complete integer compact SVG language emitted by hangul._DPen."""
    if not isinstance(value, str) or not 0 < len(value) <= 100000:
        return False
    command, count, opened, position = None, 0, False, 0
    arity = {"M": 2, "l": 2, "q": 4, "t": 2, "c": 6}
    for match in re.finditer(r"[Mlqtcz]|-?\d+", value):
        if value[position : match.start()].strip():
            return False
        position = match.end()
        token = match.group()
        if token[0] in "Mlqtcz":
            if command is not None and (not count or count % arity[command]):
                return False
            if token == "M":
                if opened:
                    return False
                opened = True
            elif not opened:
                return False
            if token == "z":
                opened, command, count = False, None, 0
            else:
                command, count = token, 0
        else:
            if command is None or len(token) > 10:
                return False
            count += 1
    return position == len(value) and not opened and command is None


class GlyphCache:
    """Own exact family identities and disposable records in a local non-symlink directory."""

    def __init__(self, root: Path, weights: list[int], params: dict, inputs: dict):
        """Create a cache for frozen ordered weights and every resolved pairing the producer uses."""
        self.root = root
        self.weights = list(weights)
        self.family = identity({"schema": SCHEMA, "weights": weights, "params": params, "inputs": inputs})
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink() or not root.is_dir():
            raise OSError("glyph cache root must be a real directory")

    def key(self, ch: str) -> str:
        """Derive a path-safe identity from a single Unicode character and this frozen family."""
        if len(ch) != 1:
            raise ValueError("a glyph cache key requires exactly one character")
        return identity([self.family, ch])

    def lock(self, ch: str):
        """Hold this character's key across a miss, production and atomic publication."""
        return key_lock(self.root / (self.key(ch) + ".lock"))

    def read(self, ch: str) -> GlyphRecord | Miss:
        """Return a fully parsed accepted family, or a miss for any corrupt/incomplete record."""
        key = self.key(ch)
        row = read_json(self.root / (key + ".json"))
        try:
            if not isinstance(row, dict) or set(row) != {"schema", "key", "ch", "weights", "glyphs", "held", "sha256"}:
                return Miss()
            digest = row.pop("sha256")
            if identity(row) != digest or row["schema"] != SCHEMA or row["key"] != key or row["ch"] != ch:
                return Miss()
            if row["weights"] != self.weights or len(row["glyphs"]) != len(self.weights):
                return Miss()
            glyphs = {}
            for weight, glyph in zip(self.weights, row["glyphs"]):
                if not isinstance(glyph, dict) or set(glyph) != {"d", "adv", "box"}:
                    return Miss()
                if not _outline(glyph["d"]):
                    return Miss()
                if (
                    not _number(glyph["adv"])
                    or not 0 < glyph["adv"] <= 1000000
                    or not isinstance(glyph["box"], list)
                    or len(glyph["box"]) != 4
                ):
                    return Miss()
                if (
                    not all(type(v) is int and abs(v) <= 1000000 for v in glyph["box"])
                    or glyph["box"][0] > glyph["box"][2]
                    or glyph["box"][1] > glyph["box"][3]
                ):
                    return Miss()
                # Reconstruct producer property order, independently of JSON object ordering.
                glyphs[weight] = {ch: {"d": glyph["d"], "adv": glyph["adv"], "box": glyph["box"]}}
            if not isinstance(row["held"], list) or len(row["held"]) > 256:
                return Miss()
            held = []
            for item in row["held"]:
                if not isinstance(item, list) or len(item) != 3 or item[0] not in self.weights or item[1] != ch:
                    return Miss()
                adjustment = item[2]
                if not (_number(adjustment) or isinstance(adjustment, str) and len(adjustment) <= 80):
                    return Miss()
                held.append(tuple(item))
            return GlyphRecord(glyphs, held)
        except (TypeError, ValueError, KeyError, OverflowError):
            return Miss()

    def store(self, ch: str, record: GlyphRecord) -> None:
        """Publish a successful complete family; the caller holds its key lock and owns fit acceptance."""
        row = {
            "schema": SCHEMA,
            "key": self.key(ch),
            "ch": ch,
            "weights": self.weights,
            "glyphs": [record.glyphs[w][ch] for w in self.weights],
            "held": record.held,
        }
        row["sha256"] = identity(row)
        atomic_json(self.root / (self.key(ch) + ".json"), row)

    def discard(self, chars: list[str]) -> None:
        """Remove this family's records after detecting inputs changed during a build."""
        for ch in chars:
            with self.lock(ch):
                (self.root / (self.key(ch) + ".json")).unlink(missing_ok=True)
