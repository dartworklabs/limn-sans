"""Data for symbols.html: limn at 100/400/700/900 and the class numbers of tools/punct.py.

  uv run --no-project --with skia-pathops --with fonttools --with uharfbuzz python3 tools/build_sym_page.py

Only the glyphs the page sets are kept (letters, figures, the symbols), so the file stays small.
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
OUT = HERE.parent / "symbols-data.js"
WEIGHTS = [100, 400, 700, 900]
KEEP = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
           ".,:;!?·-–—/'\"()&@#%+=*_[]{}\\|$<>^~`…¡¿‘’“”‚„×÷€£¥¢°©®™«»‹›•±§¶†‡‰¦¬µ¹²³½¼¾ºª−¤₩￦№′″⁄‒‐‑―")
# tools/sym_numeric.py (2026-09-29): superiors, inferiors, fractions, Roman numerals, letterlike, currency
KEEP |= set("⁰⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ⅓⅔⅕⅖⅗⅘⅙⅚⅐⅛⅜⅝⅞⅑⅒⅟↉℅℁℀"
            "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫⅬⅭⅮⅯⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹⅺⅻⅼⅽⅾⅿ℉℃℗℠ℓ℮\u2126\u212a\u212bÅ"
            "₡₣₤₦₧₨₪₫₭₮₱₲₴₵₸₹₺₼₽₾₿₥₳đ\u1d62")


from sym_math import GROUPS as _SYM_MATH       # sym-math 2026-09-29: maths, arrows, punctuation, key symbols (section 06)
KEEP |= set("".join(_SYM_MATH.values()))


def trim(P):
    g = {k: v for k, v in P["glyphs"].items() if k in KEEP}
    kern = {k: v for k, v in P["kern"].items() if all(c in KEEP for c in k)}
    return {**{k: P[k] for k in ("w", "pin", "xh", "xo", "asc", "desc", "cap", "s", "space", "tn", "pnum", "pkern", "pglyph", "kcls")},
            "glyphs": g, "kern": kern, "dots": {k: v for k, v in P["dots"].items() if k in KEEP},
            "nofeet": {k: v for k, v in P["nofeet"].items() if k in KEEP}, "spur": {}, "spurfeet": {}, "alt": P["alt"]}


def run(w, tmp):
    play, dump = Path(tmp) / f"{w}.json", Path(tmp) / f"{w}-dump.json"
    subprocess.run([sys.executable, str(HERE / "build_font.py")], check=True, stdout=subprocess.DEVNULL,
                   env={**os.environ, "LIMN_WGHT": str(w), "LIMN_PLAY_OUT": str(play), "LIMN_PUNCT_DUMP": str(dump)})
    return json.loads(play.read_text()), json.loads(dump.read_text())


data = {"play": {}, "m": {}, "sym": {}}
with tempfile.TemporaryDirectory() as tmp:
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda w: (w, run(w, tmp)), WEIGHTS))
for w, (P, D) in res:
    data["play"][w] = trim(P)
    data["m"][w] = D["m"]
    sym = D.get("sym", {})
    data["sym"][w] = {**{k: v for k, v in sym.items() if k != "amp_info"}, "amp": sym.get("amp_info", {}).get(D["opt"]["amp"], "")}
OUT.write_text(header("build_sym_page.py") + "window.SYM=" + json.dumps(data, ensure_ascii=True, separators=(",", ":")) + ";\n")
print("wrote", OUT, OUT.stat().st_size, "bytes")
