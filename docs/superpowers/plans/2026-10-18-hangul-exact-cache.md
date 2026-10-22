# Implementation record: approved exact-input Hangul cache

Scope/approval: [first-phase spec](../specs/2026-10-18-hangul-exact-cache.md), based on the user's 2026-10-18 “진행해”. This is a record of that scoped implementation, not approval for #22's remaining geometry optimization or #30's shape experiments. The repository has no Handbook; actual code and build/test commands named below are the current authority.

## Task 1: local exact family records

- [x] Step 1: Add the Hangul-owned record module and public surface in `site/tools/hangul_cache.py`; fingerprint actual producer modules, parent and Latin data, rule environment and installed dependencies. Expected: all determinants and ordered weights separate keys.
- [x] Step 2: Parse bounded non-executable complete records; persist with per-key locks, checksums and atomic replacement. Expected: malformed data becomes a miss, concurrent misses publish once, a process exit preserves completed glyphs and releases its lock.
- [x] Step 3: Preserve typed numeric values and original serialized property order. Expected: cached glyph bytes and held records equal the cold record.

Logical commit point: record owner and focused tests, together with wiring below when reviewed. No commit/push/merge is requested by this record.

## Task 2: build and smoothing integration

- [x] Step 1: Wire `build_hangul.py` to load exact hits before the pool, process one missing character family per completion, and save each successful family before returning. Expected: all charset categories work and failed fits never publish.
- [x] Step 2: Freeze requested params plus 400, pass smoothing targets to pairing workers, and auto-invalidate smoothing disk records in `hangul.py`. Expected: `LIMN_KO_CACHE=0` bypasses both caches while preserving smoothing.
- [x] Step 3: Add 100-character progress and final reuse/new/time counts. Guard source/data changes between snapshots. Expected: changed inputs abort adoption and discard that family.
- [x] Step 4: Add isolated `LIMN_KO_CHARS` probe, cache ignore rules, README guidance, and build preview exclusion coordinated with the build-fix worker. Expected: default charset/output unchanged; subset output cannot target `site/`.

Logical commit point: the complete cache capability after parent review.

## Task 3: correctness evidence

- [x] Step 1: Run focused unit/integration tests against real cache files, spawned processes and fuzzed bounded bytes. Expected: determinant/order, corruption, disabled, bad-fit and resume cases pass.
- [x] Step 2: Run real official-parent glyphs through normal smoothing and unchanged fitting; compare cache-disabled, fill and hit JS bytes for all nine weights. Expected: byte equality; record duration/reuse counts and limits in `/tmp/limn-sans-work-20261018/cache.txt`. Observed: normal-smoothed CLI controls for `가갂ㄱ○℃를` produced 18 byte-identical JS files across cold/fill/hit. Broader same-input comparison below covers real held cases.
- [x] Step 3: Confirm unchanged original producer and cache-enabled representative bytes agree. Expected: no drawing/schema/order drift. Observed: `굶쬡똴쫠헬쪽헤를㎏㎞` × nine weights produced 18 byte-identical JS files across original HEAD, direct cold under frozen actually solved params, fill and actual CLI hit. All 34 held events and their per-character order survived; actual CLI fill took 309 s including pairing, hit reused 10/new 0 in 4 s. This broad comparison preceded the final environment-key-only correction. The final key then passed a separate actual CLI `가℃` × nine weights fill/hit comparison: 18 identical JS files despite changing Latin invocation/output controls, 86 s fill and 3 s hit with reused 2/new 0.
- [x] Step 4: Run repository tests and scoped quality checks after integration. Expected: CI's `make test` remains green; report unrun full-data checks explicitly. Observed: all 16 focused cache tests including real glyph fits passed; each new assertion observed an isolated mutation failure. Parent's final Python 3.13 quality/test run passed 85 tests (84 pass, one optional real-glyph skip). Current-key malformed targets, unrelated malformed/oversized history, nested/symlinked subset output and preview cache exclusions have regressions.
- [ ] Step 5: On the build machine, run full-charset cache-disabled/fill/hit builds and `make check`, compare all JS bytes and record warm-build duration. Expected: complete equivalence and accepted glyph gates before release adoption; do not claim completion until logs exist.

Logical review point: parent reviews diff and evidence; no merge/deploy occurs in this worktree task. Geometry reuse after code edits remains outside this plan.

The final environment identity includes all eleven actual `hangul.py`/`weights.py` rule inputs, including `LIMN_XH_OUT`. It excludes selected Latin weight, optical cut, temporary output/dump paths and parallel/timing controls. A test derives the actual producer env literals from source and verifies every rule changes the identity; another comparison changes the Latin invocation controls and retains the same actual cache hits. This prevents a global smoothing solve from repeating for each `make pages` Latin subprocess. Parent's actual `make pages` passed after this correction.

Independent original-HEAD default cold smoothing produced exactly the same nine targets as the new cold build (400 target 73.11061164228641). Recovered 2026-10-01 release pairing numbers differ; their original production params/dependency environment remain unknown. No equivalence with that recovered release or complete fresh-family cache build is claimed.
