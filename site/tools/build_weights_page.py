"""Data for weights.html, from the current pipeline (run after tools/build_play.py).

  uv run --no-project --with skia-pathops --with fonttools --with uharfbuzz python3 tools/build_weights_page.py

  weights-data.js   window.LIMN_WDATA: per-weight measurements of limn-font-play.js (the lines, the pin,
                    widths, counters, paragraph colour), the stem / contrast / x-height curves of
                    tools/weights.py, the seam steps, and the reference fonts (tools/weights_refs.json,
                    measured from the OFL fonts in google/fonts: l stem at half the x-height).
  weights-seam.js   window.LIMN_WSEAM: the whole build at 290 310 690 710 for the seam comparison. The page
                    adds these weights to LIMN_PLAY; it never replaces a built weight.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).parent))
from ofl_header import header
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pathops
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

import weights as W

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
SEAM = (290, 310, 690, 710)
KEEP = set("nnoonnlamp hamburgefonstiv minimum illumine dot the i's, pin it. HAMBURG 1234 aegs8B")
TEXT = ("The quick brown fox jumps over the lazy dog. Sphinx of black quartz, judge my vow. "
        "limn pins every line of the manuscript: fix it, done, main.tex 1108, 11 pins, Hamburgefonstiv.")


def load(f):
    t = f.read_text()
    return json.loads(t[t.index("=") + 1:t.rindex(";")])


def path_of(d):
    p = pathops.Path()
    if d:
        parse_path(d, TransformPen(p.getPen(), (1, 0, 0, -1, 0, 0))); p.simplify()
    return p


def holes(p):
    cs = list(p.contours)
    if not cs: return 0.0
    big = max(cs, key=lambda c: abs(c.area))
    return sum(abs(c.area) for c in cs if c.clockwise != big.clockwise and abs(c.area) >= 2)


def colour(F):
    """Ink coverage of TEXT (outlines + pins, kerned) over advance x 1.4 em, as L* on white."""
    ink = adv = 0.0; prev = None; area = {}
    for ch in TEXT:
        if ch == " ":
            adv += F["space"]; prev = None; continue
        g = F["glyphs"].get(ch)
        if not g: continue
        if ch not in area:
            a = abs(path_of(g.get("d")).area)
            d = F.get("dots", {}).get(ch)
            if d: a += len(d["pins"]) * math.pi * F["pin"]["r"] ** 2
            area[ch] = a
        ink += area[ch]
        if prev: adv += F["kern"].get(prev + ch, 0)
        d = F.get("dots", {}).get(ch)
        adv += d["adv0"] + 2 * (F["pin"]["r"] - d["pins"][0][3]) if d and d.get("only") else g["adv"]
        prev = ch
    c = ink / (adv * 1400)
    return round(c, 4), round(116 * (1 - c) ** (1 / 3) - 16, 2)


def step(A, B, chars):
    """Median change between two weights: outline XOR area over the mean outline length (units)."""
    out = []
    for ch in chars:
        ga, gb = A["glyphs"].get(ch), B["glyphs"].get(ch)
        if not ga or not gb: continue
        pa, pb = path_of(ga["d"]), path_of(gb["d"])
        if not list(pa.contours) or not list(pb.contours): continue
        dx = (pa.bounds[0] + pa.bounds[2] - pb.bounds[0] - pb.bounds[2]) / 2
        x = pathops.op(pa, pb.transform(1, 0, 0, 1, dx, 0), pathops.PathOp.XOR)
        per = 0.0
        for c in pa.contours:
            pts = [q for v, a in c.segments for q in a if q is not None]
            per += sum(math.dist(pts[i], pts[i - 1]) for i in range(len(pts)))
        out.append(abs(x.area) / max(per, 1.0))
    out.sort()
    return round(out[len(out) // 2], 2) if out else None


play = load(SITE / "limn-font-play.js")
src = str(HERE / "Quicksand[wght].ttf")
table = []
for w in sorted(play, key=int):
    F = play[w]; g = F["glyphs"]; m = W.metrics(int(w))
    top = lambda ch: round(-g[ch]["box"][1], 1)
    cov, L = colour(F)
    table.append({"w": int(w), "S": F["s"], "S_exact": round(m["S"], 1), "H": round(m["H"], 1), "contrast": round(m["H"] / m["S"], 3),
                  "xh": F["xh"], "xo": F["xo"], "asc": F["asc"], "cap": F["cap"], "desc": F["desc"],
                  "pin_r": F["pin"]["r"], "gap": F["pin"]["gap"], "pin_top": round(F["xh"] + F["pin"]["gap"] + 2 * F["pin"]["r"], 1),
                  "l_top": top("l"), "b_top": top("b"), "k_top": top("k"), "H_top": top("H"), "t_top": top("t"), "u_top": top("u"),
                  "adv_n": g["n"]["adv"], "adv_o": g["o"]["adv"], "adv_m": g["m"]["adv"],
                  "e_counter": round(holes(path_of(g["e"]["d"]))), "o_counter": round(holes(path_of(g["o"]["d"]))),
                  "S_xh": round(F["s"] / F["xh"], 3), "coverage": cov, "L": L})
curve = [{"w": w, "S": round(W.stem(w), 2), "H": round(W.metrics(w)["H"], 2), "XH": W.metrics(w)["XH"]} for w in range(100, 901, 25)]
refs = json.loads((HERE / "weights_refs.json").read_text())

seam = {}
with tempfile.TemporaryDirectory() as tmp:
    procs = {}
    for w in SEAM:
        o = Path(tmp) / f"w{w}.json"
        procs[w] = (subprocess.Popen([sys.executable, str(HERE / "build_font.py")], stdout=subprocess.DEVNULL,
                                     env={**os.environ, "LIMN_WGHT": str(w), "LIMN_PLAY_OUT": str(o)}), o)
    for w, (p, o) in procs.items():
        if p.wait(): raise SystemExit(f"build_font failed at {w}")
        seam[w] = json.loads(o.read_text())
chars = [c for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"]
steps = {"300": {"out": step(seam[290], play["300"], chars), "in": step(play["300"], seam[310], chars)},
         "700": {"out": step(play["700"], seam[710], chars), "in": step(seam[690], play["700"], chars)}}
for k in steps:
    steps[k]["ratio"] = round(steps[k]["out"] / steps[k]["in"], 2)
data = {"table": table, "curve": curve, "seam": steps,
        "refs": {fam: {w: {"S_xh": round(v["S_l"] / v["xh"], 3), "S_upm": round(1000 * v["S_l"] / v["upm"], 1),
                           "contrast": round(v["o_thin"] / v["o_side"], 2), "adv_n": round(1000 * v["adv_n"] / v["upm"])}
                       for w, v in d.items()} for fam, d in refs.items()},
        "glyphs": len(play["700"]["glyphs"])}
(SITE / "weights-data.js").write_text(header("build_weights_page.py") + "window.LIMN_WDATA=" + json.dumps(data, ensure_ascii=True, separators=(",", ":")) + ";\n")
for w, P in seam.items():
    for k in ("glyphs", "nofeet", "spur", "spurfeet"):
        P[k] = {c: v for c, v in P[k].items() if c in KEEP}
    P["alt"] = {}
(SITE / "weights-seam.js").write_text(header("build_weights_page.py") + "window.LIMN_WSEAM=" + json.dumps(seam, ensure_ascii=True, separators=(",", ":")) + ";\n")
print("weights-data.js", (SITE / "weights-data.js").stat().st_size, "weights-seam.js", (SITE / "weights-seam.js").stat().st_size)
print("seam steps", steps)
for r in table:
    print(r["w"], "S", r["S"], "xh", r["xh"], "pin top", r["pin_top"], "l top", r["l_top"], "L*", r["L"])
