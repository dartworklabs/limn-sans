"""App icons, the browser favicon and the app's inline SVGs from limn-brand.js, rendered by Chromium at their true
pixel size.

  uv run --no-project --with playwright --with pillow python3 tools/build_icons.py [--out icons]

Writes into --out (default site/icons), everything from LIMN.icon / LIMN.favicon / LIMN.wordmark:

  limn-icon-<theme>-<size>.png, limn-icon-<theme>-<size>@2x.png
      for every theme (light = 뼈종이, dark = 먹) and size in SIZES: LIMN.icon(N, {dpr: 1, flat: true}) drawn on an
      N x N canvas (N = size x scale), so 16, 20 and 32 device pixels are the pixel drawings (16@2x is the 32 drawing)
      and the other sizes the scaled 1024 drawing
  favicon-16.png, favicon-32.png, favicon.ico
      the browser favicon: LIMN.favicon(N, {dpr: 1}) on an N x N canvas for N in FAVICONS - the 16 and 32 px pixel
      drawings on 먹 (LIMN.FAVICON_PX), one favicon for light and dark tabs - and the .ico holding both
  apple-touch-icon.png
      TOUCH px, light, LIMN.icon(TOUCH, {bleed: true}): the body fills the square, no transparent corners (iOS rounds
      the icon itself and shows transparent corners as black)
  limn-icon-<theme>.svg
      the vector icon, LIMN.icon(1024, {vector: true, flat: true})
  limn-icon-<theme>-<px>.svg
      for px in UI_ICONS: the vector icon with the optical correction of that px (LIMN.iconSpec), for a page that
      inlines the icon at px CSS pixels on any screen (the Limn app's marks)
  limn-wordmark-<theme>-<h>.svg
      for h in UI_WORDMARKS: the wordmark h px tall, pin gap LIMN.gdFor(h); strokes 먹 on light, 미색 on dark
  SHA256SUMS
      sha256sum's format for every file above, so a copy elsewhere can be checked against this build

Checks after rendering, exit 1 if one fails:
  - every pixel drawing (app icon and favicon): the stem columns are solid stem colour and the rows between pin and
    stem are solid ground
  - the favicon fills its square: 먹 opaque in the middle of every edge, the rounded corners transparent at the very
    corner, and 주 only inside the pin
  - each favicon.ico frame is the favicon drawing of its size
  - apple-touch-icon: opaque everywhere, ground in the corners, and down the centre column ground, pin (주), ground,
    stem (먹), ground in that order
  - every SVG: flat (no filter), the ground, stroke and pin colours of its theme only, 주 on the one pin circle only;
    an icon's stem is the optically corrected stem for its px; a wordmark is h tall and keeps at least 1.25 px of
    white under the pin (the BI's optical-size rule)
  - SHA256SUMS lists every file written and matches its bytes
Needs limn-font.js (make font).
"""

import argparse
import base64
import hashlib
import io
import sys
import xml.etree.ElementTree as ET  # parses the SVGs this script just made, never outside input
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parent.parent
SIZES = (16, 20, 32, 40, 64)
THEMES = ("light", "dark")
TOUCH = 180  # apple-touch-icon
UI_ICONS = (14, 16)  # the Limn app's inline icons: the [더보기] label chip (14) and the top bar (16)
UI_WORDMARKS = (20,)  # the Limn app's help header shows the wordmark, 20 px tall
FAVICONS = (16, 32)  # the browser favicon's device sizes (LIMN.FAVICON_PX): a 16 CSS px tab at 1x and 2x
SVG_NS = "{http://www.w3.org/2000/svg}"

RENDER = """
async (jobs) => {
  const out = [];
  for (const [n, theme, kind] of jobs) {
    const img = new Image();
    const svg = kind === "favicon" ? LIMN.favicon(n, {dpr: 1})
      : LIMN.icon(n, kind === "bleed" ? {theme, bleed: true} : {theme, dpr: 1, flat: true});
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    await img.decode();
    const c = document.createElement("canvas"); c.width = n; c.height = n;
    c.getContext("2d").drawImage(img, 0, 0, n, n);
    out.push(c.toDataURL("image/png"));
  }
  return out;
}
"""

# the SVG files and what each must be: [name, svg, facts to check it by]
SVGS = """
([themes, icons, words]) => {
  const L = LIMN, C = L.COLOR, out = [];
  const ink = th => th === "dark" ? C.cream : C.ink;
  for (const th of themes) {
    for (const px of [1024, ...icons]) {
      const name = px === 1024 ? `limn-icon-${th}.svg` : `limn-icon-${th}-${px}.svg`;
      out.push([name, L.icon(px, {theme: th, vector: true, flat: true}),
                {kind: "icon", px, theme: th, stem: L.minimPath(0, L.iconSpec(px).w)}]);
    }
    for (const h of words) {
      const gd = L.gdFor(h);
      out.push([`limn-wordmark-${th}-${h}.svg`, L.svg(L.wordmark({gd, ink: ink(th)}), {h}),
                {kind: "wordmark", h, theme: th, gd, xh: L.XH}]);
    }
  }
  return out;
}
"""


def hexrgb(h):
    """'#15161a' -> (21, 22, 26)."""
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def check(im, d, col):
    """the stem is solid, and only ground lies between the pin's last row and the stem's first (at least one row)"""
    bad = []
    sx, sw, st, sb = d["stem"][:4]
    cap = d["stem"][4] if len(d["stem"]) > 4 else None
    qy, rows = d["pin"][1], d["pin"][2]
    gap = range(qy + len(rows), st)
    px = im.load()
    for x in range(sx, sx + sw):
        for y in range(st + (1 if cap else 0), sb):
            if px[x, y][:3] != col["stem"] or px[x, y][3] != 255:
                bad.append(f"stem pixel {x},{y} = {px[x, y]}")
        if not gap:
            bad.append("no row between pin and stem")
        for y in gap:
            if px[x, y][:3] != col["bg"] or px[x, y][3] != 255:
                bad.append(f"gap pixel {x},{y} = {px[x, y]}")
    return bad


def check_favicon(im, d, C):
    """the favicon fills its square: 먹 opaque in the middle of each edge, nothing at the very corners (the rounded
    square), and every pure 주 pixel inside the pin's box - on top of check()"""
    bad, n, px = [], im.size[0], im.load()
    ink, ver = hexrgb(C["ink"]), hexrgb(C["ver"])
    for x, y in ((n // 2, 0), (n // 2, n - 1), (0, n // 2), (n - 1, n // 2)):
        if px[x, y] != ink + (255,):
            bad.append(f"edge {x},{y} = {px[x, y]}, not opaque 먹")
    for x, y in ((0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1)):
        if px[x, y][3] != 0:
            bad.append(f"corner {x},{y} = {px[x, y]}, not transparent")
    qx, qy, rows = d["pin"]
    outside = [(x, y) for y in range(n) for x in range(n) if px[x, y][:3] == ver
               and not (qx <= x < qx + len(rows[0]) and qy <= y < qy + len(rows))]
    if outside:
        bad.append(f"주 outside the pin at {outside[:4]}")
    return bad


def check_touch(im, C):
    """apple-touch-icon: opaque, ground in the corners, and down the centre column the solid runs are ground, pin,
    ground, stem, ground (antialiased pixels between runs are skipped)"""
    bad = []
    n = im.size[0]
    if im.size != (TOUCH, TOUCH):
        bad.append(f"size {im.size}")
    px = im.load()
    if any(px[x, y][3] != 255 for y in range(n) for x in range(n)):
        bad.append("transparent pixels (iOS would show them black)")
    bone, ink, ver = hexrgb(C["bone"]), hexrgb(C["ink"]), hexrgb(C["ver"])
    for x, y in ((0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1)):
        if px[x, y][:3] != bone:
            bad.append(f"corner {x},{y} = {px[x, y]}, not the ground")
    names = {bone: "ground", ink: "stem", ver: "pin"}
    runs = []
    for y in range(n):
        c = names.get(px[n // 2, y][:3])
        if c and (not runs or runs[-1] != c):
            runs.append(c)
    if runs != ["ground", "pin", "ground", "stem", "ground"]:
        bad.append(f"centre column reads {runs}")
    return bad


def check_svg(name, text, facts, C):
    """flat, only its theme's colours, 주 on the pin circle only; an icon has the stem of its optical size, a wordmark
    its height and at least 1.25 px of white under the pin"""
    bad = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return [f"not XML: {e}"]
    th = facts["theme"]
    ground = C["bone"] if th == "light" else C["ink"]
    stroke = C["ink"] if th == "light" else C["cream"]
    allowed = {C["ver"], stroke} | ({ground} if facts["kind"] == "icon" else set())
    fills = [(el.tag.replace(SVG_NS, ""), el.get("fill")) for el in root.iter() if el.get("fill")]
    if any(el.tag.replace(SVG_NS, "") in ("filter", "defs") or el.get("filter") for el in root.iter()):
        bad.append("has a filter (the app's icons are flat)")
    if {f for _, f in fills} - allowed:
        bad.append(f"colours outside the theme: {sorted({f for _, f in fills} - allowed)}")
    if [t for t, f in fills if f == C["ver"]] != ["circle"]:
        bad.append(f"주 is not on exactly one pin circle: {[t for t, f in fills if f == C['ver']]}")
    if facts["kind"] == "icon":
        if root.get("viewBox") != "0 0 1024 1024" or root.get("width") != str(facts["px"]):
            bad.append(f"viewBox {root.get('viewBox')} width {root.get('width')}")
        stems = [el.get("d") for el in root.iter(SVG_NS + "path") if el.get("fill") == stroke]
        if stems != [facts["stem"]]:
            bad.append(f"stem is not the optically corrected stem for {facts['px']} px")
    else:
        vb = [float(v) for v in root.get("viewBox").split()]
        if abs(float(root.get("height")) - facts["h"]) > 0.05:
            bad.append(f"height {root.get('height')}, not {facts['h']}")
        pin = next(root.iter(SVG_NS + "circle"))
        white = -(float(pin.get("cy")) + float(pin.get("r"))) - facts["xh"]  # font units, pin foot to x-height
        if white * facts["h"] / vb[3] < 1.25 - 0.01:
            bad.append(f"white under the pin {white * facts['h'] / vb[3]:.2f} px < 1.25")
    return bad


def main():
    """Render, write and check every file; exit 1 if a check fails."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SITE / "icons"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(s * k, th, "icon", f"limn-icon-{th}-{s}{'' if k == 1 else '@2x'}.png") for th in THEMES for s in SIZES for k in (1, 2)]
    jobs.append((TOUCH, "light", "bleed", "apple-touch-icon.png"))
    jobs += [(n, "dark", "favicon", f"favicon-{n}.png") for n in FAVICONS]
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chromium")
        pg = br.new_page(device_scale_factor=1)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("about:blank")
        for js in ("limn-font.js", "limn-brand.js"):
            pg.add_script_tag(path=str(SITE / js))
        urls = pg.evaluate(RENDER, [[n, th, kind] for n, th, kind, _ in jobs])
        svgs = pg.evaluate(SVGS, [list(THEMES), list(UI_ICONS), list(UI_WORDMARKS)])
        ICON_PX = pg.evaluate("() => LIMN.ICON_PX")
        FAVICON_PX = pg.evaluate("() => LIMN.FAVICON_PX")
        C = pg.evaluate("() => LIMN.COLOR")
        br.close()
    if errs:
        sys.exit("page errors: " + "; ".join(errs))
    colors = {"light": {"bg": hexrgb(C["bone"]), "stem": hexrgb(C["ink"])}, "dark": {"bg": hexrgb(C["ink"]), "stem": hexrgb(C["cream"])}}
    ims, favs, bad, written = {}, {}, [], []
    for (n, th, kind, name), u in zip(jobs, urls):
        im = Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[1]))).convert("RGBA")
        im.save(out / name, optimize=True)
        written.append(name)
        if kind == "bleed":
            bad += [f"{name}: {m}" for m in check_touch(im, C)]
            continue
        if kind == "favicon":
            favs[n] = im
            bad += [f"{name}: {m}" for m in check(im, FAVICON_PX[str(n)], colors["dark"]) + check_favicon(im, FAVICON_PX[str(n)], C)]
            continue
        ims[(th, n)] = im
        if str(n) in ICON_PX:
            bad += [f"{name}: {m}" for m in check(im, ICON_PX[str(n)], colors[th])]
    ico = out / "favicon.ico"
    # Pillow drops sizes above the first image and resamples it for sizes no appended image has: start from 32
    favs[32].save(ico, format="ICO", sizes=[(16, 16), (32, 32)], append_images=[favs[16]])
    written.append(ico.name)
    with Image.open(ico) as f:
        for n in FAVICONS:
            fr = f.ico.getimage((n, n)).convert("RGBA")
            if fr.size != (n, n) or fr.tobytes() != favs[n].tobytes():
                bad.append(f"favicon.ico: the {n} frame is not the {n} favicon drawing")
    # the one favicon serves light and dark tabs: an earlier build's dark .ico is not part of this set
    (out / "favicon-dark.ico").unlink(missing_ok=True)
    for name, text, facts in svgs:
        (out / name).write_text(text + "\n", encoding="utf-8")
        written.append(name)
        bad += [f"{name}: {m}" for m in check_svg(name, text, facts, C)]
    sums = "".join(f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}\n" for n in sorted(written))
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8")
    listed = dict(reversed(line.split("  ", 1)) for line in (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines())
    if sorted(listed) != sorted(written) or any(hashlib.sha256((out / n).read_bytes()).hexdigest() != h for n, h in listed.items()):
        bad.append("SHA256SUMS does not match the files written")
    for m in bad:
        print("FAIL", m)
    pngs = sum(n.endswith(".png") for n in written)
    print(f"{pngs} PNGs + favicon.ico + {len(svgs)} SVGs + SHA256SUMS -> {out}" + (f", {len(bad)} failures" if bad else ", checks passed"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
