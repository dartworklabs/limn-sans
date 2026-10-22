# Coverage recovery — execution and verification record

Scope: [coverage recovery record](../specs/2026-10-18-coverage-recovery.md). Authorization: issue #26's existing contract, the repository diagnosis, and the user's “진행해” on 2026-10-18. These checkboxes track the resumed work; they do not invent earlier planning or design approval. No commit, push, merge, or deployment is part of this worker's authority.

## Task 1: Reproduce missing coverage and pin cmap behavior

- [x] Step 1: Add colocated `site/tools/test_coverage_page.py` integration tests using real serialized minimal TTF files, and observe assertions fail while `build_coverage_page.py` is absent. Expected: the success test fails because the requested command cannot run; rejection tests cannot find their required diagnostic.
- [x] Step 2: Pin the nine-weight agreement, all category counts, block-total conservation, explicit comparator presence, manifest mismatch, explicit missing manifest, duplicate weight, and path traversal contracts. Expected: real temporary input files exercise the actual CLI, without faking FontTools or the filesystem.
- [x] Step 3: Add generated Unicode-set partition properties and stale-revision/duplicate-JSON/empty-cmap cases. Expected: category sums equal unique cmap size for arbitrary scalar sets. Mutated copies must fail the added assertions.

Logical change boundary: tests plus the generator behavior below, kept uncommitted for parent review.

## Task 2: Implement independently regenerable coverage

- [x] Step 1: Add `site/tools/build_coverage_page.py`, parse bounded `fonts.js` metadata, confine TTF paths, require exactly weights 100–900, and read every full cmap. Expected: all nine cmaps agree or generation fails.
- [x] Step 2: Compute manifest categories independently and Unicode blocks separately. Check optional/current or explicitly selected manifest coverage plus recorded revision/version. Expected: counts come only from input fonts; zero-count categories are retained; no hard-coded acceptance count.
- [x] Step 3: Render actual 400-weight comparator glyphs with Playwright; verify font loads and embed PNG comparison tiles. Expected: a missing cmap mapping is a visible missing marker, and source-font geometry is untouched.
- [x] Step 4: Generate responsive HTML using `site/limn-pages.css` and existing navigation. Keep raw build identifiers, manifest keys, and hashes in expandable provenance. Expected: primary content explains counts and comparison; the Korean/English correction policy is visible near the heading.
- [x] Step 5: Run focused Ruff formatting/linting, mypy, and the real-font/property tests. Expected: all pass under the new file-scoped quality setup.

Logical change boundary: generator, colocated tests, scope/verification records. The parent owns build/dependency wiring and generated-file ignores.

## Task 3: Integrate and show the actual result

- [x] Step 1: Parent verifies current font artifacts against their source-data contracts and runs the real figures exporter. Expected: an actual manifest from those inputs exists; fixture counts are never substituted for exporter evidence. Observed: parent reported nine full TTF checks passing and a successful 55-figure `--no-app` export under `/tmp/limn-sans-work-20261018/figures`.
- [x] Step 2: Run `uv run --no-project --with fonttools --with pillow --with playwright python3 site/tools/build_coverage_page.py --manifest <real-manifest>` and compare its embedded report with that manifest. Expected: exact category/total agreement and matching font identity. Observed: actual embedded coverage equals the real export manifest, including total 12,142 and Hangul syllables 11,172; all nine weight fingerprints are recorded.
- [x] Step 3: Parent integrates `make pages`, pinned reference preparation, focused quality/test checks, and preview rules. Expected: standalone regeneration works and generated HTML/temporary inputs remain outside Git. Observed: actual `make pages` completed successfully after the cache-control identity fix; the final Python 3.13 quality/test run passed 85 tests (84 pass, one optional real-glyph skip). Actual `make preview` succeeded with a destination containing spaces, retained exactly the three runtime comparison TTFs and three OFL files, and excluded glyph records, smoothing data/locks and unfinished cache writes. The final coverage page was regenerated against the real export manifest; its published page and CSS returned HTTP 200. Operational addresses/state and raw evidence remain outside the repository.
- [x] Step 4: Parent shows actual before/after desktop and phone renders through the verified Tailnet review location. Expected: both use equal scale, comparison images load, and phone body width does not overflow. Observed: parent showed actual `T3.html_render` before/after comparisons at 1440×900 and 390×844; the final page loaded all 588 comparison images with no body overflow. Parent verified the Tailnet HTTPS page and persistent preview service. This records the shown PoC and does not claim a merge or deployment.

Validation evidence is kept outside the repository at `/tmp/limn-sans-work-20261018/coverage.txt`; operational preview/service details also remain outside the product repository.
