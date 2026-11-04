# Windows validation — Limn Sans 1.002

On 2026-11-04, the published 1.002 package passed finite English, symbol,
feature and combining-mark checks on SurfaceStudio running Windows 11 Home
10.0.26300. This adds Windows consumer evidence after release; it does not change
the release files or extend the language quality scope.

## Package checked

- [Release and checksums](https://github.com/dartworklabs/limn-sans/releases/tag/v1.002)
- [LimnSans-1.002.zip](https://github.com/dartworklabs/limn-sans/releases/download/v1.002/LimnSans-1.002.zip)
- [Provenance manifest](https://github.com/dartworklabs/limn-sans/releases/download/v1.002/LimnSans-1.002-provenance.json)
- [Outer SHA256SUMS](https://github.com/dartworklabs/limn-sans/releases/download/v1.002/SHA256SUMS)

ZIP SHA-256:
`5df43d30366da0e248d1d1db6fb61798abad29708d628fe4bbb7e940e0eb1690`.
The provenance records source
`7e3ce5811f9a35a9ddcf532d6576cd1884cfa57e` with `sourceClean=true`.
The outer checksums, internal package checksums and provenance file hashes passed.
Each of the nine TTFs and nine WOFF2s was SHA-256 verified after transfer to Windows.
These comparisons establish byte consistency, not independent publisher authentication.
All 18 binaries retain 919 codepoints and 933 glyphs per face, version 1.002,
and weights 100–900.

## Native installation and rendering

All nine TTFs were temporarily installed per user in an existing interactive
Windows desktop session. A fresh WPF process selected the installed **Limn Sans**
family by name, rather than opening fonts by file URI. Every requested weight
selected its exact installed file and expected name-table version without font
simulation. WPF completed **245/245 checks across 450 observations**.

The finite corpus checked actual glyph IDs, advances and offsets; canonical
NFC/NFD raster equality; zero added advance for `x` plus grave or acute; contextual
dot removal for i with dot below plus ring, and i with ogonek plus acute;
below-only dotted i; `pnum`, `tnum`, `ss01` and `zero`; U+25CC DOTTED CIRCLE and
an attached acute; and standalone grave/acute glyph identity and zero advance.
Native underline thickness was 61/1000 em at every weight.

An earlier direct SSH session-0 probe failed and was rejected as native consumer
evidence. The successful result came from interactive desktop session 1.
Negative controls rejected a zero underline thickness and `.notdef` in place of
U+25CC for every weight.

## Windows browser

Windows Edge **155.0.4283.62** ran headless with an isolated disposable profile.
The test loaded all nine released WOFF2s explicitly through `FontFace`, with
`font-synthesis: none` for DOM text. It completed **101/101 checks**: 83 emitted by
the browser and 18 derived from its raw canvas measurements (nine dotted-circle
checks and nine standalone-acute checks).

All faces loaded; the nine weight raster digests differed, and the finite sample
differed from serif fallback. Canonical pixels, feature behavior and numeral
advances passed. U+25CC had ink, its attached acute added ink without width, and
standalone acute had ink with zero width. This was a desktop viewport check;
it makes no mobile layout claim.

## Cleanup and limits

All nine temporary font resources, installed files and per-user registry entries
were removed. The temporary scheduled task, owned Edge processes and disposable
browser profile were also removed and their absence checked.

This is finite acceptance on one Windows host with WPF and Edge. It does not
qualify Office, Adobe applications, every Windows application, physical mobile/iOS,
arbitrary mixed-mark stacks or Greek/extended-Latin languages. Native standalone
zero-width mark rasterization clips ink, so those WPF checks establish glyph
identity and advance; Edge canvas supplies the standalone-ink observation.
Existing clipping and deep-stack limitations in the
[installation guide](release-install.md) still apply.

The released ZIP and its bundled documentation, checksums and provenance remain
immutable. This live report records the later validation; raw logs and screenshots
are retained separately and are not published with this report.
