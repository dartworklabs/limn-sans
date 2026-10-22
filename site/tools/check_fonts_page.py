"""Render fonts.html in Chromium and compare the font files with the engine, line by line.

  uv run --no-project --with playwright python3 tools/check_fonts_page.py [--out /tmp/limn-fonts]

Serves site/ on a free 127.0.0.1 port (its own process, stopped by its own PID), opens fonts.html,
waits for the fonts and the Hangul data, and reads window.LIMN_FONTS_REPORT: per weight and sentence
the engine's pen advance vs the browser's layout width, and the engine's SVG vs the font's fillText
drawn on the same origin at 200 px (ink range, and the pixels inked in one but more than 1 px from the
other's ink). Asks Chromium (CDP CSS.getPlatformFontsForNode) which fonts drew each line: anything but
a LimnSans-* face means a fallback glyph (tofu). Saves screenshots and report.json. Exits 1 if a line
drifts more than 1 %, has more than FAR % stray ink, or falls back.
"""
import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parent.parent
FAR = 0.2   # % of inked pixels more than 1 px from the other line's ink; one missing pin at 400 is 0.35
AVOID = {18104, 18105, 18004, 18005, 18889}   # ports other services on this machine use


def free_port():
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            p = s.getsockname()[1]
        if p not in AVOID:
            return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/limn-fonts")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    port = free_port()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(SITE)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bad = []
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        with sync_playwright() as p:
            br = p.chromium.launch(channel="chromium")
            pg = br.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=1)
            errs = []
            # failed loads are reported with their URL by the response hook (the browser's favicon probe is not)
            pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") and not m.text.startswith("Failed to load resource") else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("response", lambda r: errs.append(f"{r.status} {r.url}") if r.status >= 400 and not r.url.endswith("favicon.ico") else None)
            pg.goto(f"http://127.0.0.1:{port}/fonts.html", wait_until="load")
            pg.wait_for_function("window.LIMN_FONTS_READY === true", timeout=180_000)
            rep = pg.evaluate("window.LIMN_FONTS_REPORT")
            # which fonts drew each browser line (CDP): only Limn Sans, else a fallback glyph
            cdp = pg.context.new_cdp_session(pg)
            cdp.send("DOM.enable")
            cdp.send("CSS.enable")
            root = cdp.send("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
            nodes = cdp.send("DOM.querySelectorAll", {"nodeId": root, "selector": ".fnt"})["nodeIds"]
            used = {}
            for n in nodes:
                for fnt in cdp.send("CSS.getPlatformFontsForNode", {"nodeId": n})["fonts"]:
                    k = fnt.get("postScriptName") or fnt["familyName"]
                    k += "" if fnt.get("isCustomFont") else " (system)"
                    used[k] = used.get(k, 0) + fnt["glyphCount"]
            pg.screenshot(path=str(out / "fonts-page.png"), full_page=True)
            for i, el in enumerate(pg.query_selector_all("#cmp .wt")):
                el.screenshot(path=str(out / f"fonts-w{100 * (i + 1)}.png"))
            pg.check("#over")
            pg.select_option("#px", "64")
            pg.wait_for_timeout(300)
            for w in (100, 400, 900):
                pg.query_selector_all("#cmp .wt")[w // 100 - 1].screenshot(path=str(out / f"fonts-over-w{w}.png"))
            pg.query_selector("#feat").screenshot(path=str(out / "fonts-features.png"))
            br.close()
    finally:
        srv.terminate()
        srv.wait(timeout=10)
    (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print("fonts that drew the browser lines (glyphs):", used)
    if [k for k in used if not k.startswith("LimnSans-")]:
        bad.append(f"fallback fonts drew glyphs: {used}")
    nan = float("nan")
    print(f"{'w':>4} {'kind':>5}  {'Δ end %':>8} {'Δ ink %':>8} {'Δ left':>7} {'miss %':>7} {'>1px %':>7}  sentence")
    for r in rep:
        print(f"{r['w']:>4} {r['kind']:>5}  {r['dAdv']:>+8.3f} {r.get('dInk', nan):>+8.3f} {r.get('dLeft', nan):>+7.1f} "
              f"{r.get('miss', nan):>7.2f} {r.get('far', nan):>7.2f}  {r['s']}")
        if abs(r["dAdv"]) > 1 or abs(r.get("dInk", 0)) > 1 or r.get("far", 0) > FAR:
            bad.append(f"{r['w']} {r['kind']} {r['s']!r}: end {r['dAdv']} %, ink {r.get('dInk')} %, pixels >1 px {r.get('far')} %")
    txt = [r for r in rep if r["kind"] == "text"]
    worst = max(rep, key=lambda r: abs(r["dAdv"]))
    wi = max(txt, key=lambda r: abs(r["dInk"]))
    wm = max(txt, key=lambda r: r["miss"])
    wf = max(txt, key=lambda r: r["far"])
    print(f"max |Δ end| {abs(worst['dAdv']):.3f} % ({worst['w']} {worst['kind']} {worst['s']!r}); "
          f"max |Δ ink| {abs(wi['dInk']):.3f} % ({wi['w']} {wi['s']!r}); max pixel miss {wm['miss']:.2f} % ({wm['w']}), "
          f"beyond 1 px {wf['far']:.2f} % ({wf['w']} {wf['s']!r})")
    if errs:
        print("console:", *errs[:10], sep="\n  ")
    print("screenshots:", out)
    print("OK" if not bad else "FAIL:\n  " + "\n  ".join(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
