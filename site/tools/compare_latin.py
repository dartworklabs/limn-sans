"""Compare two builds of the Latin data (limn-font.js or limn-font-play*.js): which glyphs, kerning pairs and
top-level values differ. Used to show the Hangul work leaves the Latin untouched except 림.

  python3 tools/compare_latin.py OLD.js NEW.js
"""
import json
import sys


def load(p):
    t = open(p, encoding="utf-8").read()
    i = t.rindex("]=") + 2 if "LIMN_PLAY_OPT[" in t else t.index("=") + 1
    return json.loads(t[i:t.rindex(";")])


def diff_font(a, b, tag=""):
    out = []
    ga, gb = a.get("glyphs", {}), b.get("glyphs", {})
    for ch in sorted(set(ga) | set(gb)):
        if ga.get(ch) != gb.get(ch): out.append(f"{tag}glyph {ch}")
    for key in sorted(set(a) | set(b)):
        if key in ("glyphs", "mods"): continue
        if a.get(key) != b.get(key): out.append(f"{tag}{key}")
    ma = {tuple(m[:2]) for m in a.get("mods", [])}; mb = {tuple(m[:2]) for m in b.get("mods", [])}
    if ma != mb: out.append(f"{tag}mods {sorted(ma ^ mb)}")
    return out


def main():
    A, B = load(sys.argv[1]), load(sys.argv[2])
    if "glyphs" in A:
        d = diff_font(A, B)
    else:                                  # play bundle: one font per weight
        d = []
        for w in sorted(set(A) | set(B), key=int):
            d += diff_font(A.get(w, {}), B.get(w, {}), f"{w}: ")
    print("\n".join(d) if d else "identical")


if __name__ == "__main__":
    main()
