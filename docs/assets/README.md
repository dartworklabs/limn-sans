# README artwork

The README wordmarks and release specimen have separate provenance.

| File | Use and source |
| --- | --- |
| `brand/wordmark-light.svg` | Trademark wordmark for light grounds; unchanged export of `site/figures/logo/wordmark-light.svg` |
| `brand/wordmark-dark.svg` | Trademark wordmark for dark grounds; unchanged export of `site/figures/logo/wordmark-dark.svg` |
| `specimen-hero.svg` | Current README specimen, 1288 × 694, paper `#fbfaf7`: English, figures, symbols and nine static weights outlined from the final **1.002** release TTFs |
| `specimen-hero.png` | Historical **0.100** bilingual specimen, 1288 × 694; retained for provenance, no longer used by the README |

## Current release specimen

Source: the current release, [v1.002](https://github.com/dartworklabs/limn-sans/releases/tag/v1.002).
Extract its ZIP, then regenerate from the actual TTFs:

```sh
uv run --no-project --with fonttools --with uharfbuzz \
  python3 docs/assets/render-release-specimen.py /absolute/path/extracted-release \
  docs/assets/specimen-hero.svg
```

HarfBuzz shapes every specimen run; FontTools serializes the selected final
TTF glyph outlines as SVG paths. No installed fonts, browser fallback, hand-drawn
lettering or AI image generation is used. The renderer rejects unsupported
characters, missing glyphs, a wrong font version or inventory, and horizontal
overflow. The SVG includes accessible title/description text; the README alt text
describes the English letters, figures, symbols and nine weights actually shown.

`specimen-hero.provenance.json` and the SVG metadata record the exact runs, weights,
positions, the release URL and revision, the manifest SHA-256 and the nine source
TTF SHA-256 values. That file is the authority for those fingerprints, so this page
does not repeat them: a release changes all twelve at once, and a copy here would
go stale the first time one did. Check the artwork against the package with:

```sh
python3 -c 'import json,hashlib,pathlib,sys
p=json.load(open("docs/assets/specimen-hero.provenance.json")); r=pathlib.Path(sys.argv[1])
bad=[k for k,v in p["ttfSHA256"].items() if hashlib.sha256((r/k).read_bytes()).hexdigest()!=v]
print("release matches the specimen" if not bad else f"differs: {bad}")' /absolute/path/extracted-release
```

## Historical brand exports

The wordmarks and old PNG came from branch `feat/export-figures`, commit
`0b76e883ffae42c508463cc8ff11309c3fd13986` (`make figures`; its manifest records
`dirty: false`, font version **0.100**). The PNG was flattened from
`site/figures/type/specimen-hero@2x.png` onto paper with a 72 px margin.
It is not a specimen of any released version. The two wordmark SVGs remain byte-for-byte copies
of that export:

```text
4db19e9d17631a1a26f0d60e58c6e1401146d578b7eb2c7c7cd01bdeaa9beba4  brand/wordmark-light.svg
8c688f882ef38de41566e68c21e79c0d292ad82d6006d8362e06eed7771c596f  brand/wordmark-dark.svg
e6292a7efc7dd2b8ab10fc088bbc1a4d452f4a9f3a1d865a52dccc8eb5e8bb56  specimen-hero.png
```

Do not redraw or recolour the wordmark; replace it only with a fresh brand export.
The Limn logo and name are Dartwork trademarks outside the SIL Open Font License
that covers the font files. The font itself declares no Reserved Font Name
([OFL.txt](../../OFL.txt)), so the trademark, not the licence, is what governs the
name and the mark.
The font retains both Quicksand and NanumSquareRound OFL attribution; excluding
Hangul does not remove the supplemental symbols' upstream provenance.
