"""Pages 0-4 (Cover, Overview, Logo, App icon, Color) of the public Figma file "Limn Design System", regenerated from
figures/manifest.json and the SVGs beside it. Standard library only.

  python3 tools/portfolio/pages_public.py plan  [--page Logo]          what each page needs uploaded, and where
  python3 tools/portfolio/pages_public.py upload --page Logo --urls URLS.txt   POST the page's SVGs to upload URLs
                                                 (--first N continues an interrupted upload at the Nth figure of plan)
  python3 tools/portfolio/pages_public.py emit  [--page Logo] --out DIR        DIR/<page>.js, one Plugin API script per page
  python3 tools/portfolio/pages_public.py audit [--page Logo] --out DIR        DIR/audit-<page>.js, the read-only QA
  python3 tools/portfolio/pages_public.py check                                node --check of every script + a scan

Nothing here draws: every number and caption on a page comes from manifest.json (make figures writes it and the SVGs
into site/figures), the marks come from the Library components of the file (instances, never redrawn), the colors are
its variables, the type its text styles. What is copy (headings, sentences) lives in the templates.

To regenerate a page after a new font build (make figures first):
  1. plan --page P prints the figures P needs as layer names (fig-<key>) and the arguments for the Figma MCP tool
     upload_assets: fileKey, currentPageId, count. Call it, write its submitUrl values one per line into URLS.txt,
     then upload --page P --urls URLS.txt sends each SVG as multipart with its layer name (a single-use URL each, valid
     ten minutes). Each SVG arrives as an editable frame named fig-<key> on the page. Pages without figures (Cover,
     Overview) skip this. A page whose figures did not change can skip it too: the frames of the previous run are reused.
  2. emit --page P --out DIR writes DIR/P.js. Paste it into the MCP tool use_figma (fileKey below, skillNames
     figma-use). It is under the tool's 50,000 character limit (checked).
  3. audit --page P --out DIR, paste DIR/audit-P.js the same way: ok must be true (it compares the rendered tables
     with the manifest, so a wrong label such as a repeated height fails). The Cover carries a date: --date YYYY-MM-DD
     for emit and audit (default today).

A rerun updates in place. The page frame keeps its node id (so links stay valid): its Sections are removed and rebuilt,
the title block and footer (instances of Page/Title and Page/Footer) get their text set again, the Cover frame is
emptied and rebuilt. A fresh fig-<key> upload replaces the Figure/<key> frame of the previous run; a figure with no
fresh upload is reused; an upload nobody used is deleted. Nothing is created twice; if a needed figure is missing the
script stops before it changes anything (a failed script leaves the file as it was).

Targets (the ids of the file; a Library node is checked by name before use):
  file    zq6DnehToUVoBzckv929Lv
  pages   Cover 0:1, Overview 1:31, Logo 1:32, App icon 1:33, Color 1:34
  Library Page/Frame 13:26, Logo/Wordmark set 3:38, Logo/Lockup 3:56, Logo/Rim 3:62, Icon/App set 4:98,
          variable collection Color VariableCollectionId:1:2
"""
import argparse
import ast
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent.parent
FIG = SITE / "figures"
TEMPLATES = HERE / "templates"
CHAR_LIMIT = 49500   # use_figma takes 50,000 characters of code

FILE_KEY = "zq6DnehToUVoBzckv929Lv"
LIBRARY = {"pageFrame": "13:26", "wordmarkSet": "3:38", "lockup": "3:56", "rim": "3:62", "iconSet": "4:98",
           "colorCollection": "VariableCollectionId:1:2"}
# the pages of the file in order; the number of a page is its index
ALL_PAGES = ["Cover", "Overview", "Logo", "App icon", "Color", "Typeface", "Motion", "In use", "Developers", "Library",
             "License"]
PAGES = {
    "Cover": {"id": "0:1", "kind": "cover", "lede": ""},
    "Overview": {"id": "1:31", "kind": "pageframe", "lede": "Limn turns a pin on a PDF into the source line that made it."},
    "Logo": {"id": "1:32", "kind": "pageframe", "lede": "The wordmark, the rim mark and the lockup, and how to use them."},
    "App icon": {"id": "1:33", "kind": "pageframe",
                 "lede": "An i on a bone squircle: the pin above the stem, drawn again at each size."},
    "Color": {"id": "1:34", "kind": "pageframe", "lede": "Six tokens and one rule: vermilion is only for the pin."},
}
TEMPLATE = {"Cover": "cover", "Overview": "overview", "Logo": "logo", "App icon": "appicon", "Color": "color"}
REPO = "github.com/dartworklabs/limn"   # the limn app's public repository, not this one
TAGLINE = "The design system for Limn: logo, icon, color, typeface and motion."
HIST = r"\b(before|after|option|options|candidate|candidates|previous|previously|earlier|former|formerly|old|v\d+|alternative|alternatives|proposal)\b"


def forbidden():
    """What may never go public: the generic shapes of check_figures.py (read as data, so this file needs no
    fontTools) plus this deployment's own private names from tools/private-strings.txt, which is not committed."""
    tree = ast.parse((SITE / "tools" / "check_figures.py").read_text())
    out = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "FORBIDDEN_GENERIC" for t in node.targets):
            out = list(ast.literal_eval(node.value))
    if out is None:
        sys.exit("FORBIDDEN_GENERIC not found in tools/check_figures.py")
    private = SITE / "tools" / "private-strings.txt"
    names = []
    if private.exists():
        names = [s.strip() for s in private.read_text().splitlines() if s.strip() and not s.lstrip().startswith("#")]
    if not names and os.environ.get("LIMN_PRIVATE_STRINGS") != "none":
        how = "is missing" if not private.exists() else "names nothing"
        sys.exit(f"{private} {how}, so a page would be checked against the generic patterns alone. Put this "
                 "deployment's own hostnames and code names there (one per line, not committed), or set "
                 "LIMN_PRIVATE_STRINGS=none to accept a generic-only scan.")
    return out + names


def load():
    return json.loads((FIG / "manifest.json").read_text())


def us(s):
    """US spelling for the page copy, and the captions without the typeface's parent name."""
    s = re.sub(r"\s*\(Quicksand[^)]*\)", "", s)
    return s.replace("colour", "color").replace("Colour", "Color").replace("centred", "centered")


def num(x):
    return "%g" % x


def key_of(fid):
    return fid.replace("/", "-")


class Data:
    """The manifest's figures by id, with the helpers the pages share."""

    def __init__(self, m):
        self.m = m
        self.f = {f["id"]: f for f in m["figures"]}

    def fig(self, fid):
        if fid not in self.f:
            sys.exit("the manifest has no figure " + fid)
        return self.f[fid]

    def cap(self, fid):
        return us(self.fig(fid)["caption"])

    def ids(self, prefix):
        return [i for i in self.f if i.startswith(prefix)]


def assets(page, d):
    """The SVGs a page needs: [(key, path relative to figures/)]. Layer name fig-<key>, frame name Figure/<key>."""
    if page == "Logo":
        ids = ["logo/construction", "logo/clearspace"]
        ids += sorted(d.ids("logo/minsize-"), key=lambda i: d.fig(i)["meta"]["h"])
        ids += d.ids("logo/misuse-")
        return [(key_of(i), d.fig(i)["file"]) for i in ids]
    if page == "App icon":
        ids = ["icon/grid", "icon/ramp"]
        ids += sorted(d.ids("icon/px-"), key=lambda i: int(i.rsplit("-", 1)[1]))
        ids += ["icon/favicon-light", "icon/favicon-dark"]
        return [(key_of(i), d.fig(i)["file"]) for i in ids]
    if page == "Color":   # the misuse drawing again, as this page's own upload
        return [("color-misuse-stroke-ver", d.fig("logo/misuse-stroke-ver")["file"])]
    return []


def figs_of(page, d):
    """{key: natural width} of the page's figures: the manifest width is the size the SVG imports at."""
    out = {}
    for key, path in assets(page, d):
        fid = next(i for i, f in d.f.items() if f["file"] == path)
        out[key] = d.fig(fid)["w"]
    return out


def data_cover(d, args):
    day = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    return {"version": "Limn Sans " + d.m["fonts"]["version"], "date": "%d %s" % (day.day, day.strftime("%B %Y")),
            "repo": REPO, "tagline": TAGLINE, "pages": ALL_PAGES}


def data_overview(d, args):
    pin = d.m["demo"]["pins"][0]
    return {"label": d.m["demo"]["label"], "line": pin["line"], "note": pin["note"], "pages": ALL_PAGES}


def data_logo(d, args):
    lg = d.m["logo"]
    spec = [["Stroke s", num(lg["s"]), "sets every other measure"],
            ["x-height", num(lg["xh"]), "height of i, m and n"],
            ["Ascender", num(lg["asc"]), "the l, and the top of the pin"],
            ["Pin diameter", num(2 * lg["pin_r"]), "2r, the dot over the i"],
            ["Pin centre", num(-lg["pin_cy"]), "measured up from the baseline"],
            ["Pin gap", num(lg["gap"]), "= %s s, between the pin and the stem" % num(lg["gd"])],
            ["Clear space", num(lg["clear_space"]), "= x-height / 2, on every side"]]
    mins = sorted(d.ids("logo/minsize-"), key=lambda i: d.fig(i)["meta"]["h"])
    mingd = [[k, v] for k, v in sorted(lg["min_gd"].items(), key=lambda kv: float(kv[0]))]   # labels: the manifest keys
    variants = [("theme=light, ground=tile", "logo/wordmark-light", "paper"),
                ("theme=dark, ground=tile", "logo/wordmark-dark", "ink"),
                ("theme=ver, ground=tile", "logo/wordmark-ver", "ver")]
    misuse = [[i.split("misuse-", 1)[1], d.cap(i), key_of(i)] for i in d.ids("logo/misuse-")]
    return {
        "upm": d.m["fonts"]["upm"], "gd": lg["gd"], "nums": {"clear": num(lg["clear_space"]), "xh": num(lg["xh"])},
        "cons": d.cap("logo/construction"), "clear": d.cap("logo/clearspace"),
        "marks": [d.cap("logo/wordmark-light"), "Lockup: the wordmark and the rim mark.",
                  "The rim mark, the Korean syllable, with its own pin."],
        "min": [{"h": d.fig(i)["meta"]["h"], "gd": d.fig(i)["meta"]["gd"], "cap": d.cap(i), "key": key_of(i)} for i in mins],
        "mingd": mingd,
        "vars": [[n, d.cap(i), g] for n, i, g in variants],
        "misuse": misuse,
        "tables": {"spec": {"head": ["Measure", "Value", "Note"], "rows": spec},
                   "pingap": {"head": ["Height"] + [k + " px" for k, _ in mingd],
                              "rows": [["Pin gap, in s"] + [num(v) for _, v in mingd]]}},
        "figs": figs_of("Logo", d), "need": [k for k, _ in assets("Logo", d)],
    }


def data_appicon(d, args):
    ic = d.m["icon"]
    g = d.fig("icon/grid")["meta"]
    grid = [["Canvas", num(g["canvas"])], ["Body", num(g["body"])], ["i", num(g["i"])], ["Stem", num(g["stem"])],
            ["Pin", num(g["pin"])], ["Gap", num(g["gap"])]]
    tiers = []
    for i, t in enumerate(ic["tiers"]):
        label = ("Up to %d px" % t["to"] if i == 0 else "%d px and up" % t["from"] if i == len(ic["tiers"]) - 1
                 else "%d to %d px" % (t["from"], t["to"]))
        tiers.append([label, num(t["stem_s"]) + " s", num(t["gd"]) + " s"])
    px = [[k, v["body"], v["stem"], v["pin"], v["gap"], v["round_top"], "icon-px-" + k, d.cap("icon/px-" + k)]
          for k, v in sorted(ic["px"].items(), key=lambda kv: int(kv[0]))]
    fav = [[k, v["body"], v["stem"], v["pin"], v["gap"]] for k, v in sorted(ic["favicon"].items(), key=lambda kv: int(kv[0]))]
    x = " × "
    return {
        "grid": grid, "gridCap": d.cap("icon/grid"), "rampCap": d.cap("icon/ramp"),
        "px": px, "fav": fav, "touch": d.fig("icon/touch-180")["meta"]["px"], "touchCap": d.cap("icon/touch-180"),
        "tables": {"grid": {"head": ["Measure", "Value"], "rows": grid},
                   "tiers": {"head": ["Icon size", "Stem", "Pin gap"], "rows": tiers},
                   "fav": {"head": ["Size", "Body", "Stem", "Pin", "Gap"],
                           "rows": [[k + " px", "%d px" % bd, "%d%s%d px" % (st[0], x, st[1]), "%d%s%d px" % (pn[0], x, pn[1]),
                                     "%d px" % gp] for k, bd, st, pn, gp in fav]}},
        "figs": figs_of("App icon", d), "need": [k for k, _ in assets("App icon", d)],
    }


def data_color(d, args):
    m = d.m
    tokens = [[t["key"], t["name"], t["hex"], t["use"]] for t in m["color_tokens"]]
    contrast = [[c["fg"], c["bg"], c["ratio"], c["use"], c["need"], c["pass"]] for c in m["contrast"]]
    name = {t[0]: t[1] for t in tokens}
    rows = [[name[c[0]], name[c[1]], c[3][0].upper() + c[3][1:], "%s:1" % num(c[2]), "%s:1" % num(c[4]), "Pass" if c[5] else "Fail"]
            for c in contrast]
    return {"tokens": tokens, "contrast": contrast, "wordmarkCap": d.cap("logo/wordmark-light"),
            "strokeCap": d.cap("logo/misuse-stroke-ver"),
            "tables": {"contrast": {"skip": 1, "head": ["Foreground", "Ground", "Use", "Ratio", "Needs", "Result"], "rows": rows}},
            "figs": figs_of("Color", d), "need": [k for k, _ in assets("Color", d)]}


BUILD = {"Cover": data_cover, "Overview": data_overview, "Logo": data_logo, "App icon": data_appicon, "Color": data_color}


def cfg_of(page):
    idx = ALL_PAGES.index(page)
    p = PAGES[page]
    return {"fileKey": FILE_KEY, "pageId": p["id"], "pageName": page, "frameName": page, "kind": p["kind"],
            "number": "%02d" % idx, "title": page, "lede": p["lede"], "lib": LIBRARY}


def emit_page(page, d, args):
    prelude = (TEMPLATES / "prelude.js").read_text()
    body = (TEMPLATES / (TEMPLATE[page] + ".js")).read_text()
    cfg = json.dumps(cfg_of(page))
    data = json.dumps(BUILD[page](d, args))
    if page == "Cover":   # the cover frame is not a Page/Frame: no shell, no figures
        head = prelude.split("// --- figures")[0]
        code = head + body
    else:
        code = prelude + body
    code = code.replace("__CFG__", cfg).replace("__DATA__", data)
    if len(code) > CHAR_LIMIT:
        sys.exit("%s: %d characters, over the %d limit of use_figma" % (page, len(code), CHAR_LIMIT))
    return code


def allowed_numbers(d):
    """Every number the manifest holds for these pages, as the strings the pages show, plus what is derived."""
    m, out = d.m, set()

    def walk(o):
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            out.add(num(o))
        elif isinstance(o, str):
            if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", o):
                out.update(re.findall(r"\d+(?:\.\d+)?", o))
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k)
                walk(v)
    for k in ("logo", "icon", "contrast", "colors_other"):
        walk(m[k])
    walk(m["fonts"]["version"])
    for f in m["figures"]:
        if f["id"].startswith(("logo/", "icon/", "color/")):
            walk(f["caption"])
            walk(f.get("texts", []))
            walk(f.get("meta", {}))
            out.add(num(f["w"]))
    lg = m["logo"]
    out.update({num(2 * lg["pin_r"]), num(-lg["pin_cy"]), num(lg["xh"] / 2), num(lg["gd"])})
    line = m["demo"]["pins"][0]["line"]
    out.update({str(line - 2), str(line - 1), str(line), str(line + 1), str(line + 2)})   # the source lines around the pin
    return sorted(out, key=float)


def tables_of(page, d, args):
    """Expected rendered tables {frame name: {rows, skip}} for the audit."""
    t = BUILD[page](d, args).get("tables", {})
    names = {"spec": "Measures", "pingap": "Pin gap by height", "grid": "Grid measures table",
             "tiers": "Stem and gap by size", "fav": "Favicon drawings", "contrast": "Contrast table"}
    return {names[k]: {"rows": [v["head"]] + v["rows"], "skip": v.get("skip", 0)} for k, v in t.items()}


def emit_audit(page, d, args):
    day = datetime.date.fromisoformat(args.date) if getattr(args, "date", None) else datetime.date.today()
    allowed = allowed_numbers(d)
    if page == "Cover":   # the date of the cover is typed by the run, not by the manifest
        allowed = sorted(set(allowed) | {str(day.day)}, key=float)
    cfg = {"pageId": PAGES[page]["id"], "pageName": page, "forbidden": forbidden(), "hist": HIST,
           "allowed": allowed, "year": day.year,
           "expectTables": tables_of(page, d, args) if page != "Cover" else {}, "expectTexts": []}
    if page == "Logo":   # the pin-gap labels are the manifest keys, in order
        cfg["expectTexts"] = [k + " px" for k, _ in data_logo(d, args)["mingd"]]
    return (TEMPLATES / "audit.js").read_text().replace("__CFG__", json.dumps(cfg))


def pick(args):
    if args.page:
        if args.page not in PAGES:
            sys.exit("no such page %r; pages: %s" % (args.page, ", ".join(PAGES)))
        return [args.page]
    return list(PAGES)


def cmd_plan(args):
    d = Data(load())
    for page in pick(args):
        a = assets(page, d)
        print("%s (page %s)" % (page, PAGES[page]["id"]))
        if not a:
            print("  no figures to upload")
            continue
        print("  upload_assets fileKey=%s currentPageId=%s count=%d" % (FILE_KEY, PAGES[page]["id"], len(a)))
        for i, (key, path) in enumerate(a, 1):
            print("  %2d  fig-%-28s <- figures/%s" % (i, key, path))


def multipart(path, name):
    boundary = uuid.uuid4().hex
    body = (("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: image/svg+xml\r\n\r\n"
             % (boundary, name)).encode() + path.read_bytes() + ("\r\n--%s--\r\n" % boundary).encode())
    return body, "multipart/form-data; boundary=" + boundary


def cmd_upload(args):
    if not args.page or not args.urls:
        sys.exit("upload needs --page and --urls")
    d = Data(load())
    a = assets(args.page, d)[args.first - 1:]
    urls = [u.strip() for u in Path(args.urls).read_text().split() if u.strip().startswith("https://")]
    if len(urls) != len(a):
        sys.exit("%s needs %d upload URLs, %s has %d (see plan)" % (args.page, len(a), args.urls, len(urls)))
    for (key, path), url in zip(a, urls):
        body, ctype = multipart(FIG / path, "fig-" + key)
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": ctype})
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read())
        print("fig-%-28s success=%s node=%s bytes=%s" % (key, res.get("success"), res.get("placedOnNodeId"), res.get("sizeBytes")))
        if not res.get("success"):
            sys.exit("upload of fig-%s failed: %s" % (key, res))


def cmd_emit(args):
    d = Data(load())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for page in pick(args):
        code = emit_page(page, d, args)
        p = out / (page.replace(" ", "-").lower() + ".js")
        p.write_text(code)
        print("%s: %s (%d characters)" % (page, p, len(code)))


def cmd_audit(args):
    d = Data(load())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for page in pick(args):
        code = emit_audit(page, d, args)
        p = out / ("audit-" + page.replace(" ", "-").lower() + ".js")
        p.write_text(code)
        print("%s: %s (%d characters)" % (page, p, len(code)))


def cmd_check(args):
    """Every emitted script must parse (node --check on an async wrapper), stay under the limit, and hold none of
    what may not go public."""
    d = Data(load())
    bad = forbidden()
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        for kind, fn in (("page", emit_page), ("audit", emit_audit)):
            for page in PAGES:
                code = fn(page, d, args)
                low = re.sub(r"\"forbidden\": \[[^\]]*\]", "", code).lower()   # the audit carries the list itself
                hits = [w for w in bad if w.lower() in low]
                f = Path(tmp) / ("%s-%s.js" % (kind, page.replace(" ", "-")))
                f.write_text("(async () => {\n" + code + "\n})\n")
                r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
                ok = r.returncode == 0 and not hits
                fails += not ok
                print("%-5s %-9s %6d chars  %s%s" % (kind, page, len(code), "ok" if ok else "FAIL",
                                                        ("  " + r.stderr.strip().splitlines()[0]) if r.returncode else
                                                        ("  private: " + ", ".join(hits)) if hits else ""))
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["plan", "upload", "emit", "audit", "check"])
    ap.add_argument("--page", help="one of: " + ", ".join(PAGES))
    ap.add_argument("--out", default=str(FIG / "pages"), help="where emit and audit write (default: figures/pages, not committed)")
    ap.add_argument("--urls", help="file with the submitUrl values of upload_assets, one per line, in plan order")
    ap.add_argument("--first", type=int, default=1, help="upload: start at the Nth figure of plan (default 1)")
    ap.add_argument("--date", help="the Cover date, YYYY-MM-DD (default: today)")
    args = ap.parse_args()
    {"plan": cmd_plan, "upload": cmd_upload, "emit": cmd_emit, "audit": cmd_audit, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()
