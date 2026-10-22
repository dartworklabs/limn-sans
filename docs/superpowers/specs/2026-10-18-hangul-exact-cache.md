# Hangul exact-input cache, first phase of #22

Approved scope: the user said “진행해” on 2026-10-18 after the diagnosis proposed build fixes → #22 → #26 → #30. The diagnosis explicitly separated identical-input caching and interruption recovery from later geometry-based reuse after code changes. This record preserves that approval; it does not claim all acceptance criteria of #22 are complete.

## Current authority and state

- Architecture and production authority: `site/tools/build_hangul.py`, `hangul.py`, `audit_hangul.py`, `weights.py`, `ofl_header.py`, the four official parent TTFs and generated `site/limn-font-play.js`.
- Verification authority: `.github/workflows/test.yml` runs `make test`; `make check` requires full generated data and runs on the build machine.
- There is no project Handbook. This scoped change does not initialize one.
- Existing `_one` makes each character's requested weight family together, accepting serialized fits under geometry, whitespace and ink-order constraints. It returns glyphs, failed-fit markers and ordered held records. Existing smoothing stores globally solved targets in `.params-cache.json` under a partly manual identity.

## Invariants

1. Keep all accepted drawing/fit rules, smoothing, default charset and generated JS schema/property/character ordering. Preserve `d`, float advance, integer box and held data exactly.
2. Treat requested weight order as an input. Freeze every resolved requested pairing plus 400, which symbol production uses even for subset builds.
3. Accept only complete successful families. Broken, truncated, oversized, ambiguous or incompatible records are misses. Never deserialize executable Python objects.
4. Publish each completed character atomically. A stopped worker cannot leave a valid partial record. Independent builders coalesce a same-key miss under a kernel-managed POSIX lock.
5. `LIMN_KO_CACHE=0` bypasses glyph and params disk reads/writes while calculating the same smoothing rule. It is the release comparison control.

## Decisions, reasons and constraints

- Owner: the existing Hangul tool capability. `hangul_cache.py` declares a small public surface and has no dependency on Hangul geometry or audit code. No new package, service or third-party dependency is introduced.
- Identity: character + ordered requested weights + full resolved params + actual bytes of all producer/audit/fit/serializer modules and constants, all four parent fonts, relevant Latin JS, effective rule environment and installed dependency Python/native bytes/runtime. Hashing whole producer modules is deliberately conservative; a code change invalidates the family.
- The effective rule environment is the eleven inputs read by `hangul.py` and `weights.py`, verified against their actual source. `LIMN_XH_OUT` remains a rule input. Selected Latin weight, optical cut, temporary output/dump paths and scheduling/timing controls do not change smoothing identity; Latin glyph differences are captured by the actual generated Latin bytes in the glyph identity.
- Source of truth is the producer, never the disposable cache. Exact inputs permit no stale interval. Identity changes invalidate logically; no TTL is needed. Old identities may be removed manually.
- Storage: package-local `.glyph-cache/`, digest-only filenames, bounded JSON with a payload checksum and shape/compact-path parsing, per-key `flock`, same-directory temporary write + fsync + replace. A non-regular file or final-path symlink is rejected on reads/locks. OS I/O errors on glyph persistence remain visible build failures; completed records survive for a retry.
- Both input snapshots and final verification guard against modifying producer/data/dependency inputs while building; a detected change discards this family's records before output. Keep inputs frozen for the entire run.
- The existing smoothing cache gains automatic identity, bounded input parsing and atomic locked writes. Resolved targets pass explicitly to pairing workers so the cold switch does not cause each worker to repeat the global solve.
- Smoothing records carry a payload checksum. Non-finite numbers, invalid Unicode in any prior key/value and malformed current targets are misses. If retained history would exceed the byte limit, publish only the newly computed valid record; disposable history cannot abort a successful solve.
- Every 100 completed characters, log reuse/new counts and elapsed/estimated remaining time. Also report final totals.
- `LIMN_KO_CHARS` is a probe hook requiring an explicit output directory outside `site/`; it cannot overwrite the default complete dataset. It does not enter the glyph identity because characters are independent given their full family inputs.

## Validation and unresolved work

- Required focused checks: determinant/order invalidation; exact cold/hit serialization including held records; corrupt/partial records; disabled disk I/O; interrupted process recovery; simultaneous same-key producers; actual official-parent drawn/composed syllable, jamo and symbol fits.
- Full charset cold/hit JS byte comparison and `make check` remain build-machine work until their logs exist. Representative equivalence cannot establish full release equivalence.
- Geometry-only reuse after a localized code change, #30's quality sheets and minimum-point experiments are separate later work. No geometry/fit policy change is authorized here.
- Independent original-HEAD default cold solving reproduced the new cold targets exactly at all nine weights. The recovered 2026-10-01 release data has different pairing numbers, and its precise original production params/dependency environment were not recovered. This pre-existing discrepancy is not evidence of a cache-patch drawing regression, nor does the focused comparison prove equality with that recovered release.
