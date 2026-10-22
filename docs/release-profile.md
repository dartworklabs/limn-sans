# Stable release profile — 1.002

This profile defines the English and special-symbol release at weights 100–900,
excluding Hangul. The original `latin-symbols` release is version 1.000; version
1.001 was the stable combining-attachment correction described
[here](combining-attachment.md), and version 1.002 is the current stable release.
The default `full` bilingual developer profile remains 0.100 and is
unsupported for public release. [Version 1.000 is published](https://github.com/dartworklabs/limn-sans/releases/tag/v1.000)
from commit `24fbc8e85c28907aec709db707db44f9126f467a`.
Its final manifest records 918 Unicode codepoints and 932 glyphs per face, with
nine static weights, nine hinted TTFs and nine whole WOFF2s; 1.001 holds those
counts and 1.002 adds U+25CC DOTTED CIRCLE, so the current package is 919 and 933.
English and supported
symbols are the quality scope; included Greek and extended Latin have no language
QA. U+3000 is retained at advance 819 in every weight. The unchanged ₑ 800→900
ink decrease (~1.06%) remains informational.

Install the [release package](release-install.md). The procedures below document
its isolated producer and validation contract; the default development build and
research specimens are not release-qualified. This scope excludes geometry
repairs and unrelated diagnostics. README and actual tools own the current
contract; there is no Handbook. The historical specs retain their original scope.

The release process admits explicit inputs, removes Hangul before glyph
construction, emits and reads back nine hinted TTF/WOFF2 pairs, and verifies exact
coverage, metadata, hints, CSS and shaping. Full-profile gates remain separate.
Generated fonts are not committed.

Version 1.001 restores the missing exported combining layout within this accepted
repertoire, validated by actual before/after comparison. It removes no marks and
changes no glyph geometry: it retains all accepted producer hashes and glyph data
while adding source-derived `mark`/`mkmk` attachment and contextual dot replacement.
Existing 1.000 output and release assets are never overwritten. The correction was
accepted after source, binary, consumer and same-scale rendered before/after review,
and stable packaging reuses that accepted layout. Windows testing is explicitly deferred.

Version 1.002 is a licence-metadata correction on top of that accepted 1.001
layout, plus one admitted codepoint. Outlines, metrics, kerning and hinting are
unchanged for every glyph 1.001 already had; U+25CC DOTTED CIRCLE is new, and the
other tables that differ from 1.001 are `post` — `underlineThickness` is now one
family value, the Regular's 61, because a family may not vary it
(fontbakery `opentype/family/underline_thickness`) — `name`, specifically the
nameID 0 copyright string, and the `head.checkSumAdjustment` that follows from it.
The owner removed Limn Sans's own Reserved Font Name for external
distribution compatibility: npm, Fontsource and Google Fonts onboarding expect an
OFL font to declare no Reserved Font Name of its own. The same string shortens
from 717 to 361 characters, keeping nameID 0 inside the 500-character limit those
channels enforce. Inherited upstream names are untouched in substance: Quicksand's
"Quicksand" RFN is still declared in full, and NAVER's 22 reserved Nanum names are
referenced through the bundled `OFL.txt`, which OFL 1.1 §2 permits because the
notice may live in stand-alone text files rather than machine-readable metadata
fields. `OFL.txt` and `site/OFL.txt` drop the same self-declared RFN from their
first copyright line and keep the upstream lines verbatim. Ten of the eleven
producer inputs and their accepted hashes stay frozen; the one exception is the
Latin producer `limn-font-play.js`, which admitting U+25CC necessarily rebuilds
(see the frozen-input note further down). The 1.000 and 1.001 packages and their
assets remain immutable.

```sh
LIMN_TTF_PLAY_IN=/absolute/path/limn-font-play.js \
LIMN_TTF_SYMBOLS_IN=/absolute/path/supplemental/data \
LIMN_TTF_SPACE_PROVENANCE_IN=/absolute/path/u3000-provenance.json \
SOURCE_DATE_EPOCH=<release-commit-unix-time> \
LIMN_TTF_OUT=/absolute/path/new-empty-package-directory make fonts-release
```

The supplementary directory contains nine `limn-hangul-<weight>.js` files with the
existing `window.LIMN_HANGUL[<weight>]=...` JSON format. Supply every one of the
55 current non-Hangul `hangul.PUNCT` records (including overlapping ℃). Together
with the 856 non-Hangul Latin records these add 54 unique characters. U+318D araea
is Hangul and excluded. U+3000 comes from the explicit original all-weight 가 advance provenance manifest.
If a supplementary record also supplies `spaces: {"　": 819.0}`, its value must agree;
otherwise the exporter supplies that field in memory from the provenance manifest. The provenance manifest must contain exactly nine weight keys, each with `char`,
`advance` and `source_glyph` (`가`); its SHA-256 is recorded alongside all producer
JS input hashes. `SOURCE_DATE_EPOCH` fixes final font timestamps. Never
manufacture a syllable fixture to supply the space. Full Hangul and extension
files are unnecessary; extension references are not followed by this profile.

Coverage is frozen explicitly in `build_ttf.py`: unexpected or missing non-Hangul
records fail before output is written. Original non-Hangul characters and spaces
are preserved, including U+3000. The output must start empty to prevent stale
bilingual/core/ext fonts from being packaged. `LIMN_TTF_LOGO=1` and disabled hinting
are refused. OpenType alternates are constructed only from admitted input; the
validator checks the entire glyph inventory, including unencoded glyphs.
It compares every Unicode cmap with the admitted codepoint-to-glyph mapping and
every glyph's source-generated coordinates, contour endpoints, on-curve flags,
advance and left sidebearing with the final TTF, including all feature alternates.
The release hinting pipeline preserves these values exactly; no outline tolerance
or extra auxiliary glyph allowance is applied. WOFF2 parity then binds the web face
to that checked TTF. All eleven `fonts.json.inputs` hashes must match the configured
Latin, nine supplemental JS files and U+3000 provenance file; resealing package
checksums or input metadata cannot waive source-to-font equivalence.

The package has nine TTFs, nine WOFF2s, portable `fonts.css`, legacy `fonts.js`,
portable `fonts.json` with exact codepoints, the installation README, all three
licences, and SHA-256 checksums. It contains no empty ext subset. Web files are
compressed from the final hinted TTF. Readback compares final hint/layout/name/
metric tables, outlines and glyph programs; WOFF2 glyf/loca encoding normalization
and the WOFF2 head flag are accounted for without relaxing hint identity.

The full developer profile still requires all 11,172 syllables and complementary
2,350/8,822 core/ext web faces. No full-profile assertion is relaxed.

For the real proof corpus without Hangul fixtures:

```sh
cd site
LIMN_TTF_SPACE_PROVENANCE_IN=/absolute/path/u3000-provenance.json \
uv run --no-project --with skia-pathops --with fonttools --with uharfbuzz \
  --with shapely --with scipy python3 tools/audit.py \
  --scope latin-symbols --symbols /absolute/path/supplemental/data \
  --data play=/absolute/path/limn-font-play.js --json /absolute/path/audit.json
```

Add opt12/opt16/opt20/opt28 to `--data` for the existing optical-cut audits. This
explicit scope removes Hangul runs from the actual corpus (replacing them with
separators so no artificial neighbor pairs form), admits all nine supplemental
inputs and skips the Hangul gate. Existing Latin geometry gates and informational
Greek/extended Latin/alphabetic-subscript policy remain intact. Supplemental
outlines, spaces and advances are checked in final font readback; the Latin audit
does not claim the supplemental symbols passed its Latin-specific geometry rules.
The unchanged ₑ 800→900 area decrease (~1.06%) remains informational.

fontbakery 1.1.0 is not a gate in this repository, but 1.002 is clean under it:
`check-universal` and `check-googlefonts` both exit 0 with no ERROR, FATAL or FAIL.
Two of the surviving warnings are expected and must not be "fixed":
`googlefonts/license/OFL_body_text` wants only the first line of `OFL.txt` changed,
while this font is a derivative of two OFL fonts and OFL 1.1 §1 requires carrying
both upstream notices; `googlefonts/name/rfn` reports the upstream reserved names
and says itself that they differ from the family name, "which is fine". The rest
are Google Fonts packaging items (`lacks-meta-table`, `lacks-article`, an
unregistered `achVendID`) that belong to an onboarding submission, not to the font.

`make quality` and `make test` are CI gates (`.github/workflows/test.yml`).
`make fonts-release` performs build and profile-aware readback locally; the glyph
audit needs explicit producer data and is a release validation step, not a CI gate.
The opt-in `test_release_readback` acceptance tests run the real checker CLI against
an admitted nine-weight package and resealed adversarial copies. From `site/tools`,
set `LIMN_RELEASE_TEST_PACKAGE` plus the same three input hooks shown above and run
`python -m unittest -v test_release_readback` in the font-build runtime.
`LIMN_RELEASE_TEST_LOGS` optionally retains each checker log. These tests cover the
normal package, changed inputs, resigned input metadata, equal-advance cmap swaps,
and encoded/alternate outline or metric changes; ordinary CI skips them when the
explicit release fixtures are absent.

## Accepted validation and limits

The accepted source is `356c5441cfc8244aa373cb19b5eb2ec442a6d74e` (PR #34;
main merge `db7bdef72eae9332ce9fb1326ffbc7bf77fa5f6a`). Those revisions and the
issue and pull-request numbers used throughout these documents belong to the
private development history; the public repository starts from the published
snapshot, so they identify inputs rather than links a reader can follow. What a
reader can check is in the package: the provenance manifest binds every input by
SHA-256. The export contract is written against the accepted candidate's
**glyphs**, not its table bytes: every glyph the candidate already had must come
out with an identical outline and advance. Whole-table identity held while 1.001
changed nothing but `name` and `head`; 1.002 adds a glyph, so `glyf`, `loca`,
`cmap`, `hmtx`, `maxp`, `post` and the layout tables all differ by construction,
and `post` differs again for the family underline. What is checked at release is
the glyph-level comparison plus the deliberate list of table changes.
The actual font export runtime is Python 3.14.7;
the retained producer-JS runtime is Python 3.13.14. They are separate stages.
The asset provenance records exact runtime files/hashes, source and package hashes.

The inputs that stay frozen are the ten the glyph does not touch. Admitting U+25CC into
`RELEASE_LATIN` re-opens the eleventh: `limn-font-play.js` has to be rebuilt, so its
accepted `playSHA256` no longer applies and the Latin record count becomes 856. The supplemental
symbol records, the U+3000 provenance manifest and the Hangul inputs are untouched. It ships under
1.002; re-accepting the producer hash is a release-owner action on the package that version builds.

Accepted consumer evidence covers Safari 26.6.2, Chrome and Firefox at desktop and
mobile viewport sizes, finite native CoreText probes, nine process-scoped macOS
font selections and nine embedded PDF pages with 108 lines of text readback.
The practical horn/above corpus has 1,512 CoreText/HarfBuzz matches, including
432 Vietnamese tone cases, without true outline intersections. These are finite
layout checks, not Greek/extended-Latin language QA. Final package checks repeat
native version/context smoke and OTS for all 18 binaries; the browser matrix binds
through exact layout-table identity rather than a new browser qualification.

Synthetic deep/mixed attached/free stacks can retain engine-dependent placement.
Positioned accents can exceed the unchanged 970/−330 metrics and clip in constrained
containers. Windows is deferred; physical mobile/iOS and persistent Font Book/Office
installation are untested.
