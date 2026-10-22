"""Playground data: the limn rules applied to Quicksand at several weights, plus the pieces the
type page needs to switch each rule off (round feet, Quicksand's own n family, original dots).

  uv run --no-project --with fonttools --with skia-pathops --with uharfbuzz python3 tools/build_play.py

Runs build_font.py once per weight (LIMN_WGHT / LIMN_PLAY_OUT; all weights at once, LIMN_JOBS) and bundles the results into
limn-font-play.js. Quicksand's wght axis runs 300-700; tools/weights.py erodes the 300 master and
dilates the 700 master for 100-200 and 800-900, and rounds the light period so the pin rule finds it.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).parent))
from ofl_header import header
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "limn-font-play.js"
WEIGHTS = list(range(100, 1000, 100))   # 100-900 (tools/weights.py extends Quicksand's 300-700 axis)

OPT_PX = os.environ.get("LIMN_OPT_PX")   # text cut (C-05): limn-font-play-opt<px>.js, window.LIMN_PLAY_OPT[px]
if OPT_PX:
    OUT = HERE.parent / f"limn-font-play-opt{OPT_PX}.js"
# LIMN_JOBS: how many weights build at once (default all nine; 1 = one after another). Each weight is its own
# build_font.py process, so the result does not depend on the order.
JOBS = max(1, int(os.environ.get("LIMN_JOBS", len(WEIGHTS))))


def run(w, tmp):
    out = Path(tmp) / f"w{w}.json"
    r = subprocess.run([sys.executable, str(HERE / "build_font.py")], capture_output=True, text=True,
                       env={**os.environ, "LIMN_WGHT": str(w), "LIMN_PLAY_OUT": str(out)})
    sys.stderr.write(r.stderr)
    if r.returncode:
        sys.exit(f"build_play: build_font.py failed at {w}" + (f" (text cut {OPT_PX} px)" if OPT_PX else ""))
    return w, json.loads(out.read_text())


with tempfile.TemporaryDirectory() as tmp:
    with ThreadPoolExecutor(JOBS) as ex:
        bundle = dict(ex.map(lambda w: run(w, tmp), WEIGHTS))
bundle = {w: bundle[w] for w in WEIGHTS}
if OPT_PX:
    OUT.write_text(header("build_play.py") + "window.LIMN_PLAY_OPT=window.LIMN_PLAY_OPT||{};window.LIMN_PLAY_OPT[" + json.dumps(float(OPT_PX)) + "]=" + json.dumps(bundle, ensure_ascii=True, separators=(",", ":")) + ";\n")
else:
    OUT.write_text(header("build_play.py") + "window.LIMN_PLAY=" + json.dumps(bundle, ensure_ascii=True, separators=(",", ":")) + ";\n")
print("wrote", OUT, OUT.stat().st_size, "bytes;", ", ".join(f"{w}: s {bundle[w]['s']}" for w in WEIGHTS))
