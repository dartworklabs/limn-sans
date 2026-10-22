"""Measure the built Hangul against limn's Latin, weight by weight (the rim5 study's measures), and derive the
Hangul tracking from fonts designed with their own Latin.

  uv run --no-project --with fonttools --with skia-pathops --with numpy --with pillow python3 tools/hangul_measure.py [--refs] [--json out.json]

Reads site/limn-font-play.js and site/limn-hangul-<w>.js (make play, make hangul). All numbers are limn units,
heights positive up. Measures (as /tmp/limn-audit/rim5 tunelib/mixlib defined them):
  h50        median syllable height          over the proof Hangul + a general paragraph, with repeats
  open       median floor of syllables without 받침 whose vowel stands (가 나 다 리 기)
  closed     median floor of syllables with 받침
  centroid   ink-mass centroid height
  V/S        Hangul vertical stroke (the vowel stem of 이 니 디 …) / limn's stem S
  grey       Hangul ink per advance / limn Latin ink per advance, both over the 940 line band; "grey"
             uses NanumSquareRound's own advance (the study's measure), "grey+t" includes the tracking
  gapH       median white between neighbouring syllables of the proof words (row by row where both have ink)
--refs: Pretendard, SUIT, Noto Sans KR, IBM Plex Sans KR at 400 and 700 (LIMN_KO_REFS, default the study's
copies in /tmp/limn-audit): their syllable white over their own Latin letter white. The tracking that gives
limn the same proportion is  median(gapH / gapL) x limn gapL - limn gapH (tracking 0).
"""
import io
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pathops
from fontTools import subset
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hangul as H  # noqa: E402

SITE = Path(__file__).resolve().parent.parent
BAND = 940
GEN = ("한글은 자음과 모음을 모아 네모꼴 음절로 쓴다 원고를 고칠 때마다 핀을 남기면 다음 수정에서 무엇을 바꿨는지 바로 보인다 "
       "논문 그림과 표 참고문헌 수식 번호를 한 화면에서 확인하고 공동 저자와 의견을 나눈다 오늘 받은 리뷰어 코멘트는 모두 열두 개이고 "
       "그중 세 개는 이미 해결했다 빨리 읽히는 글자는 획의 굵기와 속공간이 고르게 짜여 있다 사람 나라 우리 시간 문제 사회 경우 생각 정도")
ALL = H.PROOFS + [H.PARA]


def runs_of(s, pred):
    out, cur = [], ""
    for ch in s + " ":
        if pred(ch): cur += ch
        elif cur: out.append(cur); cur = ""
    return out


HW = [w for s in ALL for w in runs_of(s, H.is_syllable)]                 # Hangul words of the proofs
LW = [w for s in ALL for w in runs_of(s, lambda c: c.isascii() and c.isalpha())]
HCORP = [c for c in "".join(HW) + GEN if H.is_syllable(c)]
LC = "".join(LW)
VERT = {0, 1, 2, 3, 4, 5, 6, 7, 20}   # ㅏㅐㅑㅒㅓㅔㅕㅖㅣ


# ------------------------------------------------------------------ geometry
def path_d(d):
    p = pathops.Path(); parse_path(d, p.getPen()); p = H.orient(p)          # clean outlines: re-wind, never simplify (see hangul.orient)
    return p


def circle(cx, cy, r):
    k = 0.5522847 * r; p = pathops.Path()
    p.moveTo(cx + r, cy)
    p.cubicTo(cx + r, cy + k, cx + k, cy + r, cx, cy + r); p.cubicTo(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
    p.cubicTo(cx - r, cy - k, cx - k, cy - r, cx, cy - r); p.cubicTo(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
    p.close()
    return p


def polys(p, steps=16):
    import weights as W
    return [W._flat(c, steps) for c in p.contours]


class Raster:
    """Nonzero mask of a path at `scale` px per unit (rim2 lib2.Raster)."""

    def __init__(self, p, scale=2.0, pad=10):
        x0, y0, x1, y1 = p.bounds
        self.x0, self.y0, self.k = x0 - pad, y0 - pad, scale
        Wd, Ht = int(math.ceil((x1 - x0 + 2 * pad) * scale)), int(math.ceil((y1 - y0 + 2 * pad) * scale))
        wind = np.zeros((Ht, Wd), np.int16)
        for poly in polys(p):
            if len(poly) < 3: continue
            a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
            im = Image.new("L", (Wd, Ht), 0)
            ImageDraw.Draw(im).polygon([((x - self.x0) * scale, (y - self.y0) * scale) for x, y in poly], fill=1)
            wind += (1 if a > 0 else -1) * np.asarray(im, np.int16)
        self.m = wind != 0

    def _runs(self, v):
        v = np.concatenate([[False], v, [False]]).astype(np.int8); d = np.diff(v)
        return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))

    def runs_row(self, y, xa=-1e9, xb=1e9):
        i = min(max(int(round((y - self.y0) * self.k)), 0), self.m.shape[0] - 1)
        return [(self.x0 + a / self.k, self.x0 + b / self.k) for a, b in self._runs(self.m[i])
                if self.x0 + b / self.k > xa and self.x0 + a / self.k < xb]

    def runs_col(self, x, ya=-1e9, yb=1e9):
        j = min(max(int(round((x - self.x0) * self.k)), 0), self.m.shape[1] - 1)
        return [(self.y0 + a / self.k, self.y0 + b / self.k) for a, b in self._runs(self.m[:, j])
                if self.y0 + b / self.k > ya and self.y0 + a / self.k < yb]


_RC = {}


def ras(key, p, scale):
    if (key, scale) not in _RC: _RC[(key, scale)] = Raster(p, scale, pad=4 if scale == 0.5 else 10)
    return _RC[(key, scale)]


# ------------------------------------------------------------------ faces: get(ch) -> (path y down, advance)
def load_js(path):
    t = Path(path).read_text()
    return json.loads(t[t.index("]=") + 2 if "LIMN_HANGUL[" in t else t.index("=") + 1: t.rindex(";")])


class HFace:
    def __init__(self, data, key):
        self.g = data["glyphs"]; self.key = key; self._c = {}; self.track = data.get("track", 0)

    def glyph(self, ch):
        if ch not in self._c:
            g = self.g.get(ch); self._c[ch] = (path_d(g["d"]), g["adv"]) if g else None
        return self._c[ch]


class FontFace:
    """A reference font (1000 UPM, y down)."""

    def __init__(self, path, wght, text, key):
        f = TTFont(str(path))
        o = subset.Options(); o.layout_features = []; o.notdef_outline = True
        s = subset.Subsetter(o); s.populate(text=text + " "); s.subset(f)
        if wght is not None and "fvar" in f:
            if "STAT" in f: del f["STAT"]
            f = instancer.instantiateVariableFont(f, {"wght": wght})
        b = io.BytesIO(); f.save(b); b.seek(0); f = TTFont(b)
        self.gs, self.cm, self.u = f.getGlyphSet(), f.getBestCmap(), 1000 / f["head"].unitsPerEm
        self.key = key; self._c = {}; self.track = 0

    def glyph(self, ch):
        if ch not in self._c:
            gn = self.cm.get(ord(ch))
            if gn is None: self._c[ch] = None
            else:
                rp = DecomposingRecordingPen(self.gs); self.gs[gn].draw(rp)
                p = pathops.Path(); rp.replay(p.getPen()); p = H.tidy(p.transform(self.u, 0, 0, -self.u, 0, 0))
                self._c[ch] = (p, self.gs[gn].width * self.u)
        return self._c[ch]


class LFace:
    """limn Latin at one weight, pins drawn (the fit rule of LIMN_playset), kerning."""

    def __init__(self, W, w):
        self.W = W; self.key = ("L", w); self._c = {}; self.s = W["s"]; self.xh = W["xh"]

    def glyph(self, ch):
        if ch in self._c: return self._c[ch]
        W = self.W; g = W["glyphs"].get(ch)
        if not g: self._c[ch] = None; return None
        p = path_d(g["d"]) if g.get("d") else pathops.Path()
        d = W["dots"].get(ch); r = W["pin"]["r"]; gap = W["pin"]["gap"]; adv = g["adv"]
        if d:
            os_ = W["xo"] - W["xh"]
            for k, x, y, r0 in d["pins"]:
                nx = x + (r - r0) if d["only"] else x
                cy = W["xh"] + gap + r if k == "i" else r - os_ if k == "base" else W["xo"] - r if k == "top" else y
                p.addPath(circle(nx, -cy, r))
            p = H.tidy(p)
            if d["only"]: adv = d["adv0"] + 2 * (r - d["pins"][0][3])
        self._c[ch] = (p, adv)
        return self._c[ch]

    def kern(self, a, b):
        K = self.W["kern"]; KC = self.W.get("kcls") or {}
        v = K.get(a + b)
        if v is not None: return v
        l = (KC.get(a) or [a])[0] or a; r = (KC.get(b) or [None, b])[1] or b
        return K.get(l + r, 0) if l + r != a + b else 0


# ------------------------------------------------------------------ measures
def pct(v, q):
    return float(np.percentile(v, q))


def hmeasure(f, chars=None):
    chars = chars or HCORP
    tops, bots, hs, cy_rows, cy_w = [], [], [], [], []
    A = Wd = Wt = 0.0
    for ch in chars:
        g = f.glyph(ch)
        if not g: continue
        p, adv = g; x0, y0, x1, y1 = p.bounds
        tops.append(-y0); bots.append(-y1); hs.append(y1 - y0)
        A += abs(H._area(p)); Wd += adv - f.track; Wt += adv
        r = ras((f.key, ch), p, 0.5)
        prof = r.m.sum(axis=1).astype(float)
        cy_rows.append(-(r.y0 + (np.arange(len(prof)) + 0.5) / r.k)); cy_w.append(prof)
    ry, rw = np.concatenate(cy_rows), np.concatenate(cy_w)
    return {"h50": float(np.median(hs)), "top50": float(np.median(tops)), "bot50": float(np.median(bots)),
            "centroid": float((ry * rw).sum() / rw.sum()), "grey": A / Wd / BAND, "grey_t": A / Wt / BAND}


def floors(f, chars=None):
    op, cl = [], []
    for ch in chars or HCORP:
        o = ord(ch) - 0xAC00; g = f.glyph(ch)
        if not g or not 0 <= o < 11172: continue
        b = -g[0].bounds[3]
        if o % 28: cl.append(b)
        elif (o // 28) % 21 in VERT: op.append(b)
    return {"open": float(np.median(op)), "closed": float(np.median(cl))}


def vstroke(f):
    ws = []
    for ch in H.VSET:
        p = f.glyph(ch)[0]; x0, y0, x1, y1 = p.bounds; r = ras((f.key, ch), p, 4.0)
        for fr in (0.4, 0.5, 0.6):
            rr = r.runs_row(y0 + fr * (y1 - y0))
            if rr: ws.append(rr[-1][1] - rr[-1][0])
    return float(np.median(ws))


def edges(f, ch, p, step=4):
    r = ras((f.key, ch), p, 0.5); x0, y0, x1, y1 = p.bounds
    out = {}
    for y in range(int(math.floor(y0 / step)) * step, int(math.ceil(y1)) + 1, step):   # one grid for every glyph
        rr = r.runs_row(y)
        if rr: out[int(y)] = (rr[0][0], rr[-1][1])
    return out


STAT = os.environ.get("LIMN_GAP_STAT", "mean")  # mean over the rows (the study's measure); min: the nearest approach


def pair_gap(f, a, xa, b, xb, band=None, stat=None):
    """White between two neighbours, row by row where both have ink: the mean over the rows (default, the
    rim3/rim5 measure) or the nearest approach (LIMN_GAP_STAT=min). The mean counts the deep white inside a
    syllable, so it is only fitted where the references are (400, 700): see hangul.TRACK."""
    ea, eb = edges(f, *a), edges(f, *b)
    gs = [xb + eb[y][0] - (xa + ea[y][1]) for y in ea if y in eb and (band is None or band[0] <= y <= band[1])]
    if len(gs) < 5: return None
    return float(np.min(gs)) if (stat or STAT) == "min" else float(np.mean(gs))


def gap_words(f, words, band=None, kern=None, track=0.0):
    gs = []
    for wd in words:
        prev = None; x = 0.0
        for ch in wd:
            g = f.glyph(ch)
            if not g: prev = None; continue
            if prev:
                if kern: x += kern(prev[0], ch)
                v = pair_gap(f, (prev[0], prev[1]), prev[2], (ch, g[0]), x, band)
                if v is not None: gs.append(v)
            prev = (ch, g[0], x); x += g[1] + track
    return float(np.median(gs))


def latin_grey(L):
    A = Wd = 0.0
    for ch in LC:
        g = L.glyph(ch)
        if g: A += abs(H._area(g[0])); Wd += g[1]
    return A / Wd / BAND


def own_latin(f):
    xh = -f.glyph("x")[0].bounds[1]
    return {"xh": xh, "cap": -f.glyph("H")[0].bounds[1]}


REFS_DIR2 = Path(os.environ.get("LIMN_KO_REFS", "/tmp/limn-audit")) / "rim2/fonts"
REFS_DIR3 = Path(os.environ.get("LIMN_KO_REFS", "/tmp/limn-audit")) / "rim3/fonts"
REFS = [
    ("Pretendard", {400: (REFS_DIR2 / "pretendard/PretendardVariable.ttf", 400), 700: (REFS_DIR2 / "pretendard/PretendardVariable.ttf", 700)}),
    ("SUIT", {400: (REFS_DIR2 / "suit/SUIT-Variable.ttf", 400), 700: (REFS_DIR2 / "suit/SUIT-Variable.ttf", 700)}),
    ("Noto Sans KR", {400: (REFS_DIR2 / "notosanskr/NotoSansKR[wght].ttf", 400), 700: (REFS_DIR2 / "notosanskr/NotoSansKR[wght].ttf", 700)}),
    ("IBM Plex Sans KR", {400: (REFS_DIR3 / "ibmplexsanskr/IBMPlexSansKR-Regular.ttf", None), 700: (REFS_DIR3 / "ibmplexsanskr/IBMPlexSansKR-Bold.ttf", None)}),
]


# Latin | Hangul neighbours without a space: those of the proofs, and the other direction
MIXED = [w for s in ALL + ["PDF를 핀이pin 림limn Limn은 A가 x는 한글Hx 표Table 글Type 3개 v0.3에서"] for w in s.split()]


def bnd_gap(f, track=0.0, bnd=0.0):
    """Median white between a Latin letter and a Hangul syllable set side by side (rows where both have ink)."""
    gs = []
    for wd in MIXED:
        x = 0.0; prev = None
        for ch in wd:
            g = f.glyph(ch)
            if not g: prev = None; continue
            if prev and (H.is_syllable(prev[0]) != H.is_syllable(ch)) and (prev[0].isalpha() and ch.isalpha()):
                x += bnd
                v = pair_gap(f, (prev[0], prev[1]), prev[2], (ch, g[0]), x)
                if v is not None: gs.append(v)
            prev = (ch, g[0], x); x += g[1] + (track if H.is_syllable(ch) else 0)
    return float(np.median(gs))


class MixFace:
    """limn Latin with its Hangul: the glyph from whichever has it (Latin first, as the engine does)."""

    def __init__(self, L, Hf, w):
        self.L, self.Hf, self.key, self.track = L, Hf, ("M", w), 0

    def glyph(self, ch):
        if H.is_syllable(ch) and ch != "림": return self.Hf.glyph(ch)
        return self.L.glyph(ch) or self.Hf.glyph(ch)


def refs():
    text = "".join(sorted(set("".join(ALL) + GEN + "xHlo" + "".join(MIXED))))
    out = []
    for name, ws in REFS:
        for lw, (path, wv) in ws.items():
            f = FontFace(path, wv, text, (name, lw))
            lat = own_latin(f)
            gH = gap_words(f, HW); gL = gap_words(f, LW, band=(-lat["xh"], 0)); gB = bnd_gap(f)
            out.append({"name": name, "lw": lw, "gapH": gH, "gapL": gL, "gapB": gB, "ratio": gH / gL, "ratioB": gB / gL})
            print(f"  {name:17s} {lw}: syllable white {gH:5.1f}  letter white {gL:5.1f}  Latin|Hangul {gB:5.1f}"
                  f"  ratio {gH / gL:.3f}  boundary ratio {gB / gL:.3f}", flush=True)
    return out


def main():
    play = load_js(SITE / "limn-font-play.js")
    res = {"weights": {}}
    if "--refs" in sys.argv:
        print("references (own Latin):")
        R = refs(); res["refs"] = R
        for lw in (400, 700):
            res.setdefault("ratio", {})[lw] = float(np.median([r["ratio"] for r in R if r["lw"] == lw]))
            res.setdefault("ratioB", {})[lw] = float(np.median([r["ratioB"] for r in R if r["lw"] == lw]))
        print("median syllable/letter white:", res["ratio"], " Latin|Hangul / letter white:", res["ratioB"])
    for w in H.WEIGHTS:
        fp = SITE / f"limn-hangul-{w}.js"
        if not fp.exists(): continue
        Hd = load_js(fp); Hf = HFace(Hd, ("H", w)); L = LFace(play[str(w)], w)
        m = hmeasure(Hf); fl = floors(Hf); V = vstroke(Hf); gL = latin_grey(L)
        gapL = gap_words(L, LW, band=(-L.xh, 0), kern=L.kern)
        gapH = gap_words(Hf, HW)
        gapH0 = gap_words(Hf, HW, track=-Hf.track)
        rec = {**m, **fl, "S": L.s, "V": V, "V/S": V / L.s, "grey": m["grey"] / gL, "grey+t": m["grey_t"] / gL,
               "gapL": gapL, "gapH": gapH, "gapH0": gapH0, "track": Hf.track, "pair": Hd["pair"]}
        rec["gapB0"] = bnd_gap(MixFace(L, Hf, w)); rec["gapB"] = bnd_gap(MixFace(L, Hf, w), bnd=Hd.get("bnd", 0))
        if "ratio" in res:
            x = min(1.0, max(0.0, (w - 400) / 300)); ratio = res["ratio"][400] + x * (res["ratio"][700] - res["ratio"][400])
            rec["track_fit"] = ratio * gapL - gapH0
            rb = res["ratioB"][400] + x * (res["ratioB"][700] - res["ratioB"][400])
            rec["bnd_fit"] = rb * gapL - rec["gapB0"]
        res["weights"][w] = rec
        print(f"{w}: {Hd['pair']['master']:>2} pen {Hd['pair']['delta']:+6.2f} k {Hd['pair']['k']:.4f} dy {Hd['pair']['dy']:+6.1f} | "
              f"h50 {m['h50']:5.0f} open {fl['open']:+5.0f} closed {fl['closed']:+5.0f} centroid {m['centroid']:5.1f} "
              f"V/S {V / L.s:.3f} grey {rec['grey']:.3f} (+t {rec['grey+t']:.3f}) | white L {gapL:5.1f} H {gapH:5.1f} (t0 {gapH0:5.1f})"
              + f" | L|H {rec['gapB']:5.1f}" + (f" -> track {rec['track_fit']:+.1f}, boundary {rec['bnd_fit']:+.1f}" if "track_fit" in rec else ""), flush=True)
    if "--page" in sys.argv:             # numbers for hangul.html (generated, like weights-data.js)
        (SITE / "hangul-measure.js").write_text("/* generated by tools/hangul_measure.py --page, do not edit */\nwindow.LIMN_HANGUL_MEASURE="
                                                + json.dumps(res, ensure_ascii=False, separators=(",", ":"), default=float) + ";\n")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
