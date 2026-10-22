# Limn Sans 1.002 — English and symbols

Version 1.002 corrects licence metadata and adds one codepoint. The `name` table copyright string
(nameID 0) no longer declares a Reserved Font Name for Limn Sans itself, and it is
shortened from 717 to 361 characters so it fits the 500-character nameID 0 limit
that external distribution channels enforce. The inherited upstream reserved names
are unchanged: "Quicksand" is still declared in full, and NAVER's reserved Nanum
names are now referenced through the bundled `OFL.txt`, which carries the complete
list and the full licence text as OFL 1.1 §2 permits.

The added codepoint is U+25CC DOTTED CIRCLE: the family carries combining marks,
and a shaper draws a mark typed without a base over that placeholder, which fell
back to `.notdef` while the glyph was missing. The drawing is the ring of © — O's
own band and the family's light pen — cut into twelve dots, so the two read as one
diameter; the exporter anchors an above mark over that ink, as it does for a
capital.

One family metric changes with it. `post.underlineThickness` was 0.8 of each
weight's own stem, 32 at Thin to 124 at Black; a family may not vary that value,
so all nine faces now carry the Regular's 61. Browsers draw it only under
`text-decoration-thickness: from-font`, and body text keeps exactly the line it
had. `underlinePosition` is unchanged at −100.

Every glyph 1.001 already had comes out of 1.002 with an identical outline and an
identical advance, at all nine weights; hints, kerning and mark attachment are
unchanged for them. That is a statement about glyphs, not about table bytes:
adding a glyph necessarily rewrites `glyf`, `loca`, `cmap`, `hmtx`, `maxp` and the
layout tables, `post` carries the new underline, and `name` and its
`head.checkSumAdjustment` carry the licence change. The package now has 919
Unicode codepoints, 933 glyphs per face and nine static weights (100–900): nine
hinted TTFs, nine whole WOFF2s, CSS, manifests, installation instructions, three
OFL notices and internal checksums. Hangul and the pinned logo are excluded;
U+3000 remains at advance 819. Versions 1.000 and 1.001 and their assets remain
immutable.

English and supported symbols are the quality scope. Greek and extended Latin
remain included without language QA. The combining-sequence behaviour accepted for
1.001 carries over unchanged: explicit mark-to-base and mark-to-mark attachment and
contextual i/j dot replacement before above marks.

Known limits: synthetic deep or mixed attached/free stacks can differ between
engines; positioned accents can exceed the fixed 970/−330 line box and clip in
constrained containers. Combining lowercase drawings differ from flatter
precomposed capitals. The unchanged ₑ 800→900 ink-area decrease (~1.06%) remains
informational. Windows is explicitly deferred; physical mobile/iOS and persistent
Font Book/Office installation are untested.

Download `LimnSans-1.002.zip`. Verify it and `LimnSans-1.002-provenance.json`
against the outer `SHA256SUMS`; the ZIP includes its own per-file `SHA256SUMS`.
The provenance binds the clean source commit, every input by SHA-256 and the
export runtime. Ten of the eleven inputs are the ones 1.001 accepted; the Latin
producer `limn-font-play.js` is rebuilt, because admitting a codepoint re-opens it.

This repository begins at a single squashed snapshot commit; anything after it is
ordinary public history. Revisions and issue numbers cited in its documents
identify the private development history, not links a reader can follow; the
provenance manifest is what a reader can check.
