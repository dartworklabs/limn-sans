# Limn Sans 1.002 — English and symbols

[Download the 1.002 ZIP](https://github.com/dartworklabs/limn-sans/releases/download/v1.002/LimnSans-1.002.zip)
· [Release notes and checksums](https://github.com/dartworklabs/limn-sans/releases/tag/v1.002).

This package covers **919 Unicode codepoints and 933 glyphs per face**, in nine static weights: Thin 100, ExtraLight 200, Light 300,
Regular 400, Medium 500, SemiBold 600, Bold 700, ExtraBold 800 and Black 900.
Each weight has one hinted TTF for desktop installation and one whole WOFF2 for the web.
There is no variable font or core/ext subset split. U+3000 has an advance of 819
font units at every weight.

Install the TTF files using your operating system's font installer. For web use,
keep `fonts.css` and the nine WOFF2 files in the same directory, and link the CSS:

```html
<link rel="stylesheet" href="fonts/fonts.css">
```

```css
body { font-family: "Limn Sans", sans-serif; }
.numbers { font-variant-numeric: proportional-nums; }
.alternates { font-feature-settings: "ss01" 1, "zero" 1; }
```

Tabular figures are the default. OpenType `pnum`, `tnum`, `kern`, `ss01` (double-storey
**a** and **g**) and `zero` (dotted zero) are retained. CSS declares exact coverage;
unsupported characters use your fallback font.

Version 1.002 corrects licence metadata and adds one codepoint: the `name` table
copyright string declares no Reserved Font Name for Limn Sans itself and fits the
500-character nameID 0 limit, with NAVER's reserved Nanum names referenced through
the bundled `OFL.txt`, and U+25CC DOTTED CIRCLE is added as the placeholder a
shaper draws under a mark typed without a base. `post.underlineThickness` is now
the Regular's 61 at every weight rather than 0.8 of each weight's own stem, which
only affects `text-decoration-thickness: from-font`. Apart from that glyph and
that field, outlines, hints, metrics and kerning are unchanged from
1.001, which fixed Safari/CoreText combining-sequence spacing with explicit
`mark`/`mkmk` attachment and contextual `ccmp` dot replacement for i/j, including
below-accented i before an above mark. Synthetic deep or mixed attached/free stacks can still
differ between engines. Fixed lowercase combining drawings differ from flatter
precomposed capital forms; positioned accents and stacks can exceed the unchanged
970/−330 line box and clip in constrained containers. Allow sufficient line height
and avoid clipping containers when using combining sequences.

Validation covers a finite corpus in Safari, Chrome and Firefox at desktop and
mobile viewport sizes, native CoreText, process-scoped macOS font selection and
PDF readback. This does not establish arbitrary multi-mark or language support.
Windows testing is deferred. Physical mobile/iOS and persistent Font Book/Office
installation have not been tested.

The release excludes all Hangul syllables, jamo, extended/halfwidth jamo, Hangul
marks and the pinned 림 trademark logo. English and the supported symbols are the
quality scope. Existing Greek and extended Latin characters remain included, but
this is not a claim of language QA for those scripts/languages. Alphabetic subscript
ₑ has a known unchanged ink-area decrease of approximately 1.06% from weight 800
to 900; it remains a low-priority informational finding, not a geometry change in
this release. `fonts.json` lists the exact Unicode codepoints, profile, version,
weights, sizes and metrics. `SHA256SUMS` covers every other package file.

The fonts are licensed under the SIL Open Font License 1.1. Keep `OFL.txt`,
`OFL-Quicksand.txt` and `OFL-NanumSquareRound.txt` with redistributed packages.
The Limn logo/wordmark is a Dartwork trademark and is not included in this package.
