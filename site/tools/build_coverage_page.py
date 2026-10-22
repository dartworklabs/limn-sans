"""Build coverage.html from the current nine TTFs, independently of make figures.

Counts use complete Unicode cmaps. The figures manifest uses script/category
buckets, which are deliberately separate from the Unicode-block table. Glyph
tiles are rasterized by Playwright from the input fonts and embedded in the page;
viewing the page needs neither reference-font downloads nor installed fonts.
"""

import argparse
import base64
import json
import logging
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from fontTools import subset
from fontTools import version as fonttools_version
from fontTools.ttLib import TTFont, TTLibError
from fontTools.unicodedata import block

__all__ = ["build_report", "coverage", "main"]
SITE = Path(__file__).resolve().parents[1]
CATEGORIES = ("hangul", "jamo", "latin", "greek", "cyrillic", "digits", "punctuation", "spaces", "symbols")
LABELS = (
    "한글 음절",
    "한글 자모",
    "라틴 문자",
    "그리스·콥트 문자",
    "키릴 문자",
    "십진 숫자",
    "문장부호",
    "공백·서식",
    "그 밖의 기호",
)
REFERENCES = (("Inter", "Inter.ttf"), ("Pretendard", "Pretendard-Regular.ttf"), ("Noto Sans KR", "NotoSansKR.ttf"))
SAMPLE_BLOCKS = (
    "Latin-1 Supplement",
    "Greek and Coptic",
    "General Punctuation",
    "Superscripts and Subscripts",
    "Currency Symbols",
    "Letterlike Symbols",
    "Number Forms",
    "Arrows",
    "Mathematical Operators",
    "Miscellaneous Technical",
    "Geometric Shapes",
    "Miscellaneous Symbols",
    "Dingbats",
)


@dataclass(frozen=True)
class FontInput:
    """A locally selected font with its parsed Unicode cmap and content fingerprint."""

    label: str
    path: Path
    points: frozenset[int]
    fingerprint: str


def _category(cp: int) -> str:
    """Independently implement the established figures-manifest partition of a scalar."""
    if 0xAC00 <= cp <= 0xD7A3:
        return "hangul"
    if 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F or 0xA960 <= cp <= 0xA97F or 0xD7B0 <= cp <= 0xD7FF:
        return "jamo"
    name, category = unicodedata.name(chr(cp), ""), unicodedata.category(chr(cp))
    for prefixes, key in ((("LATIN ",), "latin"), (("GREEK ", "COPTIC "), "greek"), (("CYRILLIC ",), "cyrillic")):
        if name.startswith(prefixes):
            return key
    if category == "Nd":
        return "digits"
    if category.startswith("P"):
        return "punctuation"
    if category.startswith("Z") or category == "Cf":
        return "spaces"
    return "symbols"


def coverage(points: frozenset[int]) -> dict[str, int]:
    """Return a disjoint, exhaustive category partition, including zero-count buckets."""
    counts = Counter(_category(cp) for cp in points)
    return {"total": len(points), **{key: counts[key] for key in CATEGORIES}}


def _json_object(text: str, source: Path) -> dict[str, Any]:
    """Parse bounded JSON objects and reject duplicate keys rather than guessing precedence."""

    depth, quoted, escaped = 0, False, False
    for character in text:
        if escaped:
            escaped = False
        elif quoted and character == "\\":
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif not quoted:
            if character in "[{":
                depth += 1
                if depth > 64:
                    raise ValueError(f"{source}: JSON nesting exceeds 64 levels")
            elif character in "]}":
                depth -= 1

    def unique(pairs):
        """Reject duplicate keys at every JSON-object nesting level."""
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{source}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except RecursionError as error:
        raise ValueError(f"{source}: JSON nesting exceeds the parser limit") from error
    if not isinstance(value, dict):
        raise ValueError(f"{source}: expected a JSON object")  # noqa: TRY004 - invalid file format
    return value


def _read_text(path: Path) -> str:
    """Read a small metadata file; the CLI caller explicitly selects its containing root."""
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError(f"missing or oversized metadata: {path}")
    return path.read_text(encoding="utf-8")


def _font_path(root: Path, relative: str) -> Path:
    """Resolve metadata font names under the chosen fonts root, rejecting traversal and links out."""
    if not isinstance(relative, str) or not relative.startswith("fonts/"):
        raise ValueError(f"invalid font path: {relative!r}")
    tail = Path(relative.removeprefix("fonts/"))
    if tail.is_absolute() or ".." in tail.parts:
        raise ValueError(f"invalid font path: {relative!r}")
    path = (root / tail).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix.lower() != ".ttf":
        raise ValueError(f"invalid font path: {relative!r}")
    return path


def _read_font(label: str, path: Path) -> FontInput:
    """Read a bounded local TTF and reject an empty, malformed or non-scalar cmap."""
    if not path.is_file() or not 0 < path.stat().st_size <= 64_000_000:
        raise ValueError(f"missing or oversized font: {path}")
    raw = path.read_bytes()
    with TTFont(BytesIO(raw)) as font:
        points = frozenset(font.getBestCmap() or {})
    if not points or any(cp < 0 or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF for cp in points):
        raise ValueError(f"empty or invalid Unicode cmap: {path}")
    return FontInput(label, path, points, sha256(raw).hexdigest())


def _inputs(fonts: Path, refs: Path) -> tuple[dict[str, Any], list[int], list[FontInput], list[FontInput]]:
    """Parse the open fonts.js schema, requiring exactly the nine advertised full TTF weights."""
    metadata_path = fonts / "fonts.js"
    text = _read_text(metadata_path)
    match = re.fullmatch(r"\s*(?:/\*.*?\*/\s*)?window\.LIMN_FONT_FILES\s*=\s*(\{.*\})\s*;\s*", text, re.DOTALL)
    if not match:
        raise ValueError(f"invalid font metadata assignment: {metadata_path}")
    metadata = _json_object(match.group(1), metadata_path)
    files = metadata.get("files")
    if not isinstance(files, list) or len(files) != 9 or any(not isinstance(f, dict) for f in files):
        raise ValueError("fonts.js must describe weights 100–900 exactly once")
    weights = [entry.get("w") for entry in files]
    if any(type(w) is not int for w in weights) or sorted(weights) != list(range(100, 901, 100)):
        raise ValueError("fonts.js must describe weights 100–900 exactly once")
    for key in ("family", "version", "rev"):
        if not isinstance(metadata.get(key), str) or not metadata[key]:
            raise ValueError(f"fonts.js lacks a valid {key}")
    loaded = {}
    for entry in files:
        loaded[entry["w"]] = _read_font(f"Limn Sans {entry['w']}", _font_path(fonts, entry.get("ttf")))
    baseline = loaded[400].points
    if any(font.points != baseline for font in loaded.values()):
        raise ValueError("the weights' cmaps differ; rebuild all fonts before generating coverage")
    comparisons = [loaded[400]]
    for label, name in REFERENCES:
        path = (refs / name).resolve()
        if not path.is_relative_to(refs.resolve()):
            raise ValueError(f"reference font path escapes refs: {name}")
        comparisons.append(_read_font(label, path))
    return metadata, sorted(weights), comparisons, [loaded[weight] for weight in sorted(weights)]


def _manifest_check(path: Path | None, actual: dict[str, int], metadata: dict[str, Any]) -> dict[str, str]:
    """Require a supplied manifest to agree with counts and any recorded font revision."""
    if path is None:
        return {"status": "absent"}
    if not path.is_file():
        raise ValueError(f"missing manifest: {path}")
    manifest = _json_object(_read_text(path), path)
    got = manifest.get("coverage")
    if not isinstance(got, dict) or any(type(value) is not int or value < 0 for value in got.values()):
        raise ValueError(f"invalid manifest coverage: {path}")
    if set(got) - set(actual) or any(got.get(key, 0) != value for key, value in actual.items()):
        raise ValueError(f"manifest coverage mismatch: manifest={got}, TTF cmap={actual}")
    manifest_fonts = manifest.get("fonts", {})
    if isinstance(manifest_fonts, dict):
        for key in ("rev", "version"):
            if key in manifest_fonts and manifest_fonts[key] != metadata[key]:
                raise ValueError(f"stale manifest font {key}: {manifest_fonts[key]} != {metadata[key]}")
    return {"status": "matched", "sha256": sha256(path.read_bytes()).hexdigest()}


def build_report(fonts: Path, refs: Path, manifest: Path | None = None) -> tuple[dict[str, Any], list[FontInput]]:
    """Load real fonts and return reconciled report data; missing or stale inputs fail closed."""
    metadata, weights, loaded, all_weights = _inputs(fonts, refs)
    actual = coverage(loaded[0].points)
    blocks: dict[str, list[int]] = {}
    for index, font in enumerate(loaded):
        for cp in font.points:
            counts = blocks.setdefault(block(chr(cp)), [0] * len(loaded))
            counts[index] += 1
    rows: list[dict[str, Any]] = [{"name": name, "counts": counts} for name, counts in sorted(blocks.items())]
    report = {
        "schema": 1,
        "family": metadata["family"],
        "version": metadata["version"],
        "rev": metadata["rev"],
        "unicode_categories": unicodedata.unidata_version,
        "unicode_blocks_fonttools": fonttools_version,
        "weights": weights,
        "weight_inputs": [
            {"w": weight, "file": font.path.name, "sha256": font.fingerprint}
            for weight, font in zip(weights, all_weights)
        ],
        "coverage": actual,
        "blocks": rows,
        "fonts": [
            {"family": f.label, "file": f.path.name, "sha256": f.fingerprint, "total": len(f.points)} for f in loaded
        ],
        "manifest": _manifest_check(manifest, actual, metadata),
    }
    if sum(actual[key] for key in CATEGORIES) != actual["total"]:
        raise ValueError("coverage categories do not reconcile")
    for index, font in enumerate(loaded):
        if sum(row["counts"][index] for row in rows) != len(font.points):
            raise ValueError("Unicode blocks do not reconcile")
    return report, loaded


def _sample_groups(fonts: list[FontInput]) -> dict[str, list[int]]:
    """Select each visible Limn glyph or two-reference consensus glyph in the study blocks."""
    candidates = set().union(*(font.points for font in fonts))
    groups: dict[str, list[int]] = {name: [] for name in SAMPLE_BLOCKS}
    for cp in sorted(candidates):
        name = block(chr(cp))
        if name not in groups or unicodedata.category(chr(cp))[0] in "CZ":
            continue
        if cp in fonts[0].points or sum(cp in font.points for font in fonts[1:]) >= 2:
            groups[name].append(cp)
    return {name: points for name, points in groups.items() if points}


def _font_data(font: FontInput, points: list[int]) -> str:
    """Subset only the temporary browser rendering input, preserving source TTFs untouched."""
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
    raw = font.path.read_bytes()
    if sha256(raw).hexdigest() != font.fingerprint:
        raise ValueError(f"font changed during generation: {font.path}")
    with TTFont(BytesIO(raw)) as ttf:
        options = subset.Options()
        options.recalc_timestamp = False
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=[cp for cp in points if cp in font.points])
        subsetter.subset(ttf)
        output = BytesIO()
        ttf.save(output)
    return "data:font/ttf;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _render_tiles(fonts: list[FontInput], points: list[int]) -> dict[int, str]:
    """Rasterize real loaded fonts in bounded browser sheets, with explicit cmap-missing markers."""
    from PIL import Image
    from playwright.sync_api import sync_playwright

    if not points:
        return {}
    faces = "".join(
        f"@font-face{{font-family:F{i};font-weight:400;src:url('{_font_data(font, points)}')}}"
        for i, font in enumerate(fonts)
    )
    result = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 288, "height": 720}, device_scale_factor=2)
            for offset in range(0, len(points), 80):
                batch = points[offset : offset + 80]
                cells = []
                for cp in batch:
                    for index, font in enumerate(fonts):
                        if cp in font.points:
                            cells.append(f'<div style="font-family:F{index}">{escape(chr(cp))}</div>')
                        else:
                            cells.append('<div class="missing">—</div>')
                page.set_content(
                    '<!doctype html><meta charset="utf-8"><style>'
                    + faces
                    + "body{margin:0;background:white;color:#15161a}#sheet{display:grid;"
                    "grid-template-columns:repeat(4,72px);width:288px}#sheet>div{width:72px;"
                    "height:72px;display:flex;align-items:center;justify-content:center;"
                    "font-size:40px;font-weight:400;font-synthesis:none;overflow:hidden;"
                    'font-variation-settings:"wght" 400}.missing{font:16px sans-serif!important;'
                    'color:#aaa;background:#f4f3ef}</style><div id="sheet">' + "".join(cells) + "</div>"
                )
                statuses = page.evaluate("""async () => {
                    const faces = [...document.fonts];
                    await Promise.all(faces.map(face => face.load()));
                    await document.fonts.ready;
                    return faces.map(face => face.status);
                }""")
                if statuses != ["loaded"] * len(fonts):
                    raise ValueError(f"comparison fonts did not load: {statuses}")
                raw = page.locator("#sheet").screenshot(animations="disabled")
                with Image.open(BytesIO(raw)) as sheet:
                    for index, cp in enumerate(batch):
                        tile = sheet.crop((0, index * 144, 576, (index + 1) * 144))
                        output = BytesIO()
                        tile.save(output, format="PNG", optimize=True)
                        result[cp] = base64.b64encode(output.getvalue()).decode("ascii")
        finally:
            browser.close()
    return result


def _page(
    report: dict[str, Any], fonts: list[FontInput], tiles: dict[int, str], groups: dict[str, list[int]], nav: str
) -> str:
    """Render escaped report data into the dashboard's existing visual language and navigation."""
    counts = report["coverage"]
    checked = (
        "manifest coverage 일치" if report["manifest"]["status"] == "matched" else "manifest 없음 · cmap 직접 집계"
    )
    category_rows = "".join(
        f'<tr><th scope="row">{label}</th><td class="num">{counts[key]:,}</td></tr>'
        for key, label in zip(CATEGORIES, LABELS)
    )
    manifest_rows = "".join(
        f'<tr><th scope="row"><code>{key}</code></th><td class="num">{counts[key]:,}</td></tr>'
        for key in ("total", *CATEGORIES)
    )
    block_rows = "".join(
        '<tr><th scope="row">'
        + escape(row["name"])
        + "</th>"
        + "".join(f'<td class="num">{count:,}</td>' for count in row["counts"])
        + "</tr>"
        for row in report["blocks"]
    )
    total_row = (
        '<tr class="total"><th scope="row">전체 cmap</th>'
        + "".join(f'<td class="num">{font["total"]:,}</td>' for font in report["fonts"])
        + "</tr>"
    )
    studies = []
    for name, points in groups.items():
        cards = []
        for cp in points:
            missing = cp not in fonts[0].points
            status = " · Limn 없음" if missing else ""
            alt = "; ".join(f"{font.label}: {'있음' if cp in font.points else '없음'}" for font in fonts)
            cards.append(
                f'<figure class="glyph{" miss" if missing else ""}"><img width="288" height="72" '
                f'loading="lazy" src="data:image/png;base64,{tiles[cp]}" alt="{escape(alt)}">'
                f"<figcaption><code>U+{cp:04X}</code>{status}<br>"
                f"<span>{escape(unicodedata.name(chr(cp), '이름 없음'))}</span></figcaption></figure>"
            )
        studies.append(
            f"<h3>{escape(name)} <small>{len(points)}개 비교</small></h3>"
            '<div class="glyph-grid">' + "".join(cards) + "</div>"
        )
    provenance = "".join(
        f"<li><b>{escape(font['family'])}</b> <code>{escape(font['file'])}</code>"
        f'<br><code class="hash">{font["sha256"]}</code></li>'
        for font in report["fonts"]
    )
    weight_sources = "".join(
        f'<li><b>{font["w"]}</b> <code>{escape(font["file"])}</code><br><code class="hash">{font["sha256"]}</code></li>'
        for font in report["weight_inputs"]
    )
    data = json.dumps(report, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Limn Sans — 입력 폰트 커버리지 · Development preview</title><link rel="stylesheet" href="limn-pages.css">
<style>
.num{{text-align:right!important;font-variant-numeric:tabular-nums;font-family:var(--mono)}}
.table-wrap{{overflow-x:auto;max-width:100%}}.t.coverage th,.t.coverage td{{white-space:nowrap}}
.t.coverage th:first-child{{min-width:200px}}.t.coverage td:nth-child(2){{color:var(--ver)}}
.total{{font-weight:700}}.glyph-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:10px;margin:18px 0 36px}}
.glyph{{margin:0;background:white;border:1px solid var(--line);border-radius:6px;overflow:hidden}}
.glyph img{{display:block;width:100%;height:auto}}.glyph figcaption{{padding:8px 12px;border-top:1px solid var(--line);font-size:12px}}
.glyph figcaption span{{color:var(--muted);font:10px var(--mono);overflow-wrap:anywhere}}
.glyph.miss{{border-color:#d48e7c;background:#fff5f2}}.sec h3 small{{font-size:12px;font-weight:400;color:var(--muted)}}
.legend{{position:sticky;top:70px;z-index:2;background:var(--paper);padding:10px 0;display:flex;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--muted)}}
.legend b{{color:var(--ink)}}.sources{{list-style:none;padding:0;max-width:820px}}.sources li{{padding:12px 0;border-top:1px solid var(--line)}}
.hash{{overflow-wrap:anywhere;font-size:11px}}details summary{{cursor:pointer;color:var(--muted);margin-bottom:18px}}
@media(max-width:600px){{h1{{font-size:32px}}header{{gap:28px}}.bar{{gap:8px;padding-top:10px;padding-bottom:10px}}
.bar nav{{gap:8px 12px;font-size:12px}}.glyph-grid{{grid-template-columns:1fr}}.legend{{position:static}}footer{{padding-left:22px;padding-right:22px}}}}
</style></head><body>
{nav}
<aside class="release-note" aria-label="Release and preview scope"><strong>개발·연구 미리보기</strong> · 이 화면의 엔진·한글·브랜드 실험은 배포본과 다릅니다.
<a href="https://github.com/dartworklabs/limn-sans/releases/tag/v1.002">Limn Sans 1.002 받기</a>: 영어·기호 919자, 정적 9굵기(100–900). 한글·로고 글리프는 제외되며, 그리스어·확장 라틴은 언어 QA 대상이 아닙니다.</aside>
<header><div><p class="kicker">Limn Sans · Inter · Pretendard · Noto Sans KR</p>
<h1>입력 폰트 커버리지</h1><p class="lede">Limn Sans와 Inter · Pretendard · 본고딕(Noto Sans KR)의 글자 수와 기호를 나란히 봅니다. 수치는 아래에 기록한 입력 TTF 기준이며, 다운로드 가능한 1.001의 목록과 다를 수 있습니다. 1.001의 품질 범위는 영어·지원 기호이고, 기본 한영 개발 프로필은 0.100입니다. 포함된 문자 수는 언어 QA를 뜻하지 않습니다.</p></div>
<ul class="facts"><li><b>{counts["total"]:,}자</b><span>입력 Limn Sans의 Unicode 코드포인트</span></li>
<li><b>{counts["hangul"]:,}자</b><span>한글 음절</span></li><li><b>9개 굵기</b><span>100–900 모두 같은 글자 포함</span></li></ul></header>
<main><section class="sec"><h2><span class="no">01</span>문자 종류별</h2>
<p class="sub">Unicode 이름과 문자 속성으로 나눈 서로 겹치지 않는 분류입니다. 합은 전체 {counts["total"]:,}자입니다. 아래의 Unicode 블록과는 기준이 다릅니다.</p>
<table class="t"><thead><tr><th scope="col">분류</th><th class="num" scope="col">Limn Sans</th></tr></thead><tbody>{category_rows}
<tr class="total"><th scope="row">전체</th><td class="num">{counts["total"]:,}</td></tr></tbody></table></section>
<section class="sec"><h2><span class="no">02</span>Unicode 블록별 비교</h2>
<p class="sub">각 서체 전체 cmap을 Unicode 블록으로 나눕니다. 네 열 모두 블록 합과 전체 cmap 수가 일치합니다. 블록의 빈 자리와 미지원 글자는 세지 않습니다. 휴대폰에서는 표를 좌우로 밀어 볼 수 있습니다.</p>
<div class="table-wrap" tabindex="0" role="region" aria-label="Unicode 블록별 글자 수"><table class="t coverage"><thead><tr><th scope="col">Unicode 블록</th>
<th class="num" scope="col">Limn Sans</th><th class="num" scope="col">Inter</th><th class="num" scope="col">Pretendard</th><th class="num" scope="col">Noto Sans KR</th></tr></thead>
<tbody>{total_row}{block_rows}</tbody></table></div></section>
<section class="sec"><h2><span class="no">03</span>기호를 나란히</h2>
<p class="sub">각 칸은 왼쪽부터 Limn Sans · Inter · Pretendard · Noto Sans KR, 모두 400입니다. Limn에 있거나 참고 서체 두 곳 이상에 있는 글자를 표시합니다. 회색 —는 해당 폰트에 없음, 붉은 테두리는 Limn에 없음입니다.</p>
<div class="legend"><b>왼쪽부터</b><span>Limn Sans → Inter → Pretendard → Noto Sans KR</span></div>{"".join(studies)}</section>
<section class="sec"><h2><span class="no">04</span>집계 기준</h2>
<details><summary>집계 방식과 입력 파일 보기</summary><p class="sub">모든 수치는 TTF의 Unicode cmap을 직접 읽어 셉니다. {checked}. 버전 {escape(report["version"])} · 리비전 {escape(report["rev"])}. Unicode 이름·범주 버전 {escape(report["unicode_categories"])}, Unicode 블록 데이터 FontTools {escape(report["unicode_blocks_fonttools"])}. 그림은 입력 TTF를 Playwright로 직접 그립니다. 회색 표시를 제외하고 대체 서체를 사용하지 않습니다.</p>
<h3>manifest coverage 분류</h3><table class="t"><tbody>{manifest_rows}</tbody></table>
<h3>비교 그림 입력</h3><ul class="sources">{provenance}</ul><h3>전체 굵기 입력</h3><ul class="sources">{weight_sources}</ul></details></section></main>
<footer>기호 그림은 400 굵기입니다. 글자 수는 모든 굵기에서 같습니다. 참고 서체의 글자 수는 이 페이지에 사용한 파일 기준입니다.</footer>
<script type="application/json" id="coverage-data">{data}</script></body></html>"""


def main() -> None:
    """Generate the page atomically, or print a browser-free JSON report for independent checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", type=Path, default=SITE / "fonts")
    parser.add_argument("--refs", type=Path, default=SITE / "refs")
    parser.add_argument("--manifest", type=Path, help="require this figures manifest to match")
    parser.add_argument("--out", type=Path, default=SITE / "coverage.html")
    parser.add_argument("--report-only", action="store_true", help="print cmap JSON without browser rendering")
    arguments = parser.parse_args()
    try:
        manifest = arguments.manifest
        default_manifest = arguments.fonts.parent / "figures/manifest.json"
        if manifest is None and default_manifest.exists():
            manifest = default_manifest
        report, fonts = build_report(arguments.fonts, arguments.refs, manifest)
        if arguments.report_only:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
        source = _read_text(SITE / "fonts.html")
        navigation = re.search(r'<div class="bar">.*?</nav></div>', source, re.DOTALL)
        if navigation is None:
            raise ValueError("fonts.html lacks the dashboard navigation")
        nav = navigation.group().replace('<a href="coverage.html">커버리지</a>', "<b>커버리지</b>")
        nav = nav.replace("<b>폰트 파일</b>", '<a href="fonts.html">폰트 파일</a>')
        groups = _sample_groups(fonts)
        points = [cp for values in groups.values() for cp in values]
        tiles = _render_tiles(fonts, points)
        html = _page(report, fonts, tiles, groups, nav)
        temporary = arguments.out.with_suffix(".html.tmp")
        temporary.write_text(html, encoding="utf-8")
        temporary.replace(arguments.out)
        print(
            f"coverage: {report['coverage']['total']:,} cmap entries, {len(points)} comparison tiles -> {arguments.out}"
        )
    except (OSError, ValueError, TTLibError) as error:
        sys.exit(f"build_coverage_page: {error}")


if __name__ == "__main__":
    main()
