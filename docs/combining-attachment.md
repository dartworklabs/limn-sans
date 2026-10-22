# Combining attachment correction — 1.001

This correction fixes a defect in the existing supported repertoire. Version 1.000 ships 20 zero-advance combining marks and classifies
them correctly in GDEF, but its exporter omits GPOS attachment. Actual Safari
26.6.2 and native CoreText give Thin `x` an advance of 490, `x` + grave 588.5,
and `x` + acute 498.5. HarfBuzz/Chrome/Firefox retaining 490 does not establish
correct attachment. `A` + acute composes to the existing Á and misses the defect.

This repair restores exported shaping support. The accepted English/symbol
scope, 918 encoded codepoints, 932 glyphs, nine weights, outlines, stored advances,
hint programs, kerning values and existing alternate mappings remain fixed.
The Latin producer JS, official supplemental 213 inputs and U+3000 provenance
are reused with their accepted hashes. No producer or Hangul geometry is rebuilt.
The published 1.000 package remains immutable; version 1.001 is the stable correction, exported
separately from the immutable 1.000 assets.

The counts above record what this repair held fixed. One codepoint was admitted after it: U+25CC
DOTTED CIRCLE, the placeholder a shaper draws under a mark typed without a base, which the attachment
work above made reachable and which fell back to `.notdef` while it was missing. The current package
is 919 codepoints and 933 glyphs; see `RELEASE_LATIN` in `site/tools/build_ttf.py` for the authority.

## Decision and placement rules

`accents.py` owns the design rules, while `mark_attachment.py` transports them
into `Weight.features()`. Donor Quicksand coordinates are unsuitable: Limn
redraws its accents and uses a negative o-width reference for standalone marks.
For above marks the semantic entry is `(-o.advance/2, xh + pin.dotgap)` in the
font's upward y coordinates. Acute/grave attach at their lower skeleton end,
not at their different ink bounding-box centres. `pin.dotgap` is the source
construction gap; `pin.gap` includes the i pin's overshoot adjustment.

Base x anchors use the source's seven optical ink-band slices; a/g and ss01
forms use their actual bowl counters. The final exported simple glyphs provide
these measurements, including pins, rounding and proportional-digit translation.
Plain lowercase y uses the source mark line, capitals use `cap + .75*dotgap`,
and ascenders use their actual top plus that gap. Already accented bases retain
their own ink, with further upper marks outside it. No mark is scaled or pushed
into a collision to fit the line box.

Five attachment classes distinguish above, below, ogonek, horn and overlay.
Below marks preserve dot/comma whitespace and cedilla's existing overlap with
the bottom stroke. Ogonek joins the right foot; horn joins the top-right stroke.
Descender bases place further below marks beyond their bottom. Overlay remains
through the base's midline. All relevant non-Hangul ink glyphs and existing
alternates have explicit anchors; DFLT and existing script registrations retain
the features. Existing kerning flags and substitution mappings are unchanged.

Filtered mark-to-mark lookups move upper/lower stacks outward using actual mark
ink and the source minimum stack gap. Other directions do not interrupt a stack;
horn can host an upper mark and repeated horns move outward to the right. Repeated
overlay strokes intentionally occupy the same overlay slot. This deterministic
policy does not establish language QA for arbitrary combinations of attached marks.

The bounded release decision retains this layout (and, at the time, 932 glyphs). The practical
o/u/O/U + horn/above matrix (including 432 Vietnamese tone cases) has 1,512
CoreText/HarfBuzz probes with matching glyphs/origins and no true outline
intersections. Synthetic `g + acute + hook + horn` and noncanonical mixtures of
multiple attached/free below marks can have different host order and placement
between engines. These remain diagnostic limitations, not passing arbitrary-stack
claims. Blanket horn exclusion creates real collisions; a generic contextual
alternative needs 799 extra glyph names across the family. Neither is adopted
for this English/symbol correction, whose extended-Latin language QA remains
outside the accepted scope. No encoded character is removed or newly claimed.

Contextual `ccmp` reuses the existing dotless i/j before a surviving above mark,
skipping intervening below/overlay marks and stopping at another base. A shaper
can first compose i + below into į or ị. Only when an above mark follows, those
below-accented forms are contextually decomposed into existing dotless i plus the
existing below glyph. Below-only text retains its original dotted precomposed
form. This closes the actual-browser `i + dotbelow + ring` pin-retention regression
without adding glyphs or changing canonical input coverage.

## Verification and remaining scope

`make test` runs serialized HarfBuzz attachment tests, canonical i/j contexts,
alternate positioning, mixed/repeated stacks and generated short-cluster advance
properties. `make quality` checks the new module and tests with Ruff and checks
the module with mypy. Both gate CI in `.github/workflows/test.yml`.

`make fonts-release` reconstructs every admitted source glyph and verifies final
TTF/WOFF2 identity, inventory, metadata, hints, outlines and metrics. It also
recompiles and serializes GDEF/GPOS/GSUB before exact layout comparison. SFNT save
resolves large-offset PairPos splits and transparent ExtensionPos wrappers; it
does not discard flags, lookup indices, scripts, feature order, anchors or values.
Wrong anchors, omitted layout, changed kerning and leaked lookup flags are rejected.

Accepted validation includes native CoreText and actual Safari 26.6.2,
Chrome and Firefox at desktop and mobile viewport sizes. The finite corpus checks
glyphs, positioned ink and cluster advance, including canonical equivalents,
below-only dots and ordinary English/feature regressions. Nine process-scoped
macOS selections and nine embedded PDF pages (108 lines of text readback) were
also checked. Actual same-scale before/after rendering was reviewed before the
correction was accepted. A browser's agreement on width alone is insufficient. Stable packaging
retains every accepted table except source/version/timestamp metadata in `name`
and `head`; final native context/version smoke and OTS bind the new binaries.

The fixed lowercase mark drawings are not identical to flatter uppercase
precomposed forms. Positioned cap/ascender accents and outward stacks can exceed
the unchanged 970/−330 line metrics. The statement that individual glyph outlines
fit the box still holds; arbitrary positioned clusters cannot fit a finite box.
Measure finite-probe bounds and actual multiline/PDF clipping and overlap. A
demonstrated unacceptable representative case requires a separately justified
minimum exception, not silent geometry, inventory or metric changes. Greek and
extended Latin retain their existing language-QA limitation. Windows and physical
mobile/iOS remain untested, and Windows testing is deferred.
