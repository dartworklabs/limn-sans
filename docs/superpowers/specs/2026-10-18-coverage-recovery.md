# Coverage dashboard recovery — scope record

This records the implementation scope of issue #26 of the private development history, resumed on 2026-10-18 after the user said “진행해” in response to the repository diagnosis. It does not claim that a separate historical spec was approved. The issue's existing contract, the diagnosed missing implementation, and that instruction authorize this recovery. A rendered desktop/mobile PoC must still be shown before merge or deployment.

## Current authority and state

- **Question:** current contract and recovery intent.
- **Architecture / actual source:** `site/tools/build_ttf.py` writes full TTFs and `site/fonts/fonts.js`; `site/tools/export_figures.py` writes the independent figures manifest; `site/tools/check_figures.py` recomputes its coverage. These files are the current executable authorities. There is no System Handbook in this checkout; this change does not initialize one.
- **Verification / actual source:** issue #26 requires a reproducible `site/tools/build_coverage_page.py`, integration with `make pages preview`, and cmap/manifest agreement. The previously published `coverage.html` came from an external script and was absent from the repository.
- **Product policy / actual source:** `README.md` limits correction work to Korean and English. Inclusion in a cmap does not claim proofreading or support for another language. The page must preserve that distinction.

## Current invariants

1. Font geometry, spacing, feature tables, and exported typography stay outside this recovery.
2. Coverage means distinct Unicode code points in the complete TTF cmap, not glyph-order length, browser fallback, an engine sample, or a subset file.
3. Exactly the nine weights 100–900 must have identical cmaps. A disagreement is an error, not an intersection silently advertised as complete coverage.
4. Manifest coverage partitions code points into `hangul`, `jamo`, `latin`, `greek`, `cyrillic`, `digits`, `punctuation`, `spaces`, and `symbols`. These categories are disjoint and exhaustive. Unicode blocks form a separate partition and are labelled as such.
5. A present default manifest or an explicitly selected manifest must match counts and any recorded font version/revision. A missing optional manifest is explicitly recorded as absent; a missing explicitly selected manifest is an error.

## Scope and constraints

The generator reads `site/fonts/fonts.js` and its nine full TTFs, plus the pinned official `Inter.ttf`, `Pretendard-Regular.ttf`, and `NotoSansKR.ttf` supplied by `make refs`. It computes counts independently of the exporter and its checker, retaining a useful independent comparison rather than importing an exporter that starts a browser or another application.

The page uses the dashboard's existing stylesheet and navigation, a responsive layout, exact category counts, and a complete Unicode-block table for all four selected fonts. The study tiles cover the established symbol blocks: a glyph appears when Limn has it or at least two references have it. A missing cmap mapping has an explicit marker; browser fallback never stands in for a comparator. References identify specific input files, not every version or distribution of those families.

Playwright loads temporary subsets of the actual TTFs, verifies every face loads, and rasterizes bounded batches at weight 400. PNG tiles are embedded in the generated page. Source fonts are untouched. A reference font is unnecessary at page-view time. The browser-free `--report-only` route independently recomputes the report without requiring all figures or a Limn application export.

## Conflicts and unknowns

The recovered 2026-10-01 artifacts identify themselves as `0762a2d-dirty`. Their actual counts are evidence for those files, not proof of reconstruction from the current checkout. Parent integration owns the source-artifact checks and obtaining a real current figures manifest. The generator records content hashes, metadata revision, Unicode-category version, and FontTools block-data version so the input generation is explicit.

Input metadata is bounded JSON, duplicate keys are rejected, and selected font paths must resolve beneath their input roots. Explicit root/output arguments are local CLI authority; no network fetch, authentication scheme, or public endpoint is introduced by this generator.

## Acceptance

- `make pages preview` produces the page through the build integration without requiring an application figure export. Rebuilding coverage alone is possible.
- Nine actual TTF cmaps agree; both category and block partitions conserve their totals.
- A real matching figures manifest passes; stale counts or recorded revision fail. No expected total is hard-coded into production code.
- Real-font integration tests and generated partition properties pass; negative input cases fail clearly.
- The parent shows desktop/mobile before-and-after renders at the same scale, then obtains any required merge/deployment approval.
