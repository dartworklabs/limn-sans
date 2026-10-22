# Limn Sans — build. Everything is generated into site/ from site/tools/ (see README).
SHELL := /bin/bash
R := uv run --no-project --with skia-pathops --with fonttools --with uharfbuzz --with shapely --with scipy python3
RH := uv run --no-project --with skia-pathops --with fonttools --with numpy --with shapely --with scipy python3
RM := uv run --no-project --with skia-pathops --with fonttools --with numpy --with pillow --with shapely python3
RF := uv run --no-project --with skia-pathops --with fonttools --with brotli --with uharfbuzz --with ttfautohint-py python3
SITE := site
PREVIEW ?= $(HOME)/.t3/previews/limn-logo-poc-20260926
QUALITY := uv run --no-project --with ruff==0.14.1 --with mypy==1.18.2
QUALITY_FILES := site/tools/stamp_preview.py site/tools/test_stamp_preview.py site/tools/test_build_commands.py \
  site/tools/hangul_cache.py site/tools/test_hangul_cache.py site/tools/build_coverage_page.py site/tools/test_coverage_page.py \
  site/tools/test_audit_scope.py site/tools/test_release_profile.py site/tools/review_hangul_quality.py site/tools/test_review_hangul_quality.py \
  site/tools/mark_attachment.py site/tools/test_mark_attachment.py

.PHONY: help font play cuts pages all refs check test quality preview clean hangul hangul-fonts hangul-measure fonts fonts-release fonts-page coverage-page icons

help:
	@echo "make font     brand drawing (Quicksand Bold, S 120) -> site/limn-font.js"
	@echo "make play     weights 100-900       -> site/limn-font-play.js"
	@echo "make cuts     text cuts 12/16/20/28 -> site/limn-font-play-opt*.js (proof page, small sizes)"
	@echo "make hangul   Hangul 100-900        -> site/limn-hangul-<w>.js (fetches NanumSquareRound first)"
	@echo "make fonts-release  1.002 stable Latin+symbols; requires explicit PLAY_IN, SYMBOLS_IN, OUT (see README)"
	@echo "make fonts    full TTF/WOFF2 + core/ext WOFF2 + fonts.css -> site/fonts, checked against the data (needs play, hangul)"
	@echo "              TrueType-hinted by default (ttfautohint); LIMN_TTF_HINT=0 make fonts skips it"
	@echo "              LIMN_TTF_OUT changes output; LIMN_TTF_HANGUL_IN (or LIMN_KO_OUT) changes Hangul input only"
	@echo "make fonts-page      fonts.html in Chromium: engine vs @font-face per line (Playwright)"
	@echo "make coverage-page   cmap inventory and comparison tiles -> coverage.html (needs fonts; Playwright Chromium)"
	@echo "make pages    punct / weights / symbols data and coverage.html (needs fonts; fetches refs)"
	@echo "make icons    app icon PNGs (16 20 32 40 64, 1x 2x, light dark), favicon-16/32.png + favicon.ico (먹), apple-touch-icon 180,"
	@echo "              vector icon SVGs, the Limn app's inline SVGs (icon 14 16, wordmark 20), SHA256SUMS -> site/icons (needs font; Playwright)"
	@echo "make all      everything above"
	@echo "make refs     download OFL references (Google Fonts, Pretendard) and comparison licenses into site/refs"
	@echo "make hangul-fonts    download NanumSquareRound (NAVER, OFL) into site/tools/hangul"
	@echo "make hangul-measure  Hangul vs Latin per weight -> site/hangul-measure.js (hangul.html; needs play, hangul)"
	@echo "make check    glyph gates over every weight and cut (tools/audit.py) and the Hangul (tools/audit_hangul.py); fails on any"
	@echo "make test     unit tests of site/tools (no build data needed; fetches NanumSquareRound) - what CI runs"
	@echo "make quality  Ruff format/lint and mypy over the new cache, preview and coverage tools - also runs in CI"
	@echo "make preview  copy the built site to PREVIEW (never deletes there)"

# 림 is NanumSquareRound's own (tools/hangul.py), so every Latin build needs the parent too.
# The brand drawing is Quicksand Bold (S 120) = 700 on curve A; the family (play, hangul) runs on curve HALF.
font: hangul-fonts
	cd $(SITE) && set -o pipefail && LIMN_WCURVE=A LIMN_WGHT=700 $(R) tools/build_font.py | sed -n '1,3p'

play: hangul-fonts
	cd $(SITE) && set -o pipefail && $(R) tools/build_play.py | tail -1

# the four cuts build at once (each builds its nine weights at once: 36 build_font.py runs; LIMN_JOBS caps each cut)
cuts: hangul-fonts
	cd $(SITE) && set -o pipefail; pids=; for px in 12 16 20 28; do (LIMN_OPT_PX=$$px $(R) tools/build_play.py | tail -1 | cut -c1-100) & pids="$$pids $$!"; done; \
	st=0; for p in $$pids; do wait $$p || st=1; done; exit $$st

hangul-fonts:
	bash $(SITE)/tools/fetch_hangul.sh

# unit tests of the tools: fitting, web subsets, the pen at held pieces, the parent-ink gate (no build data needed)
test: hangul-fonts
	cd $(SITE)/tools && uv run --no-project --with skia-pathops --with fonttools --with numpy --with shapely --with scipy \
	  --with brotli --with uharfbuzz --with hypothesis python3 -m unittest discover -p 'test_*.py'

# Keep quality checks scoped to newly added tools; legacy scripts are not reformatted by this gate.
quality:
	$(QUALITY) ruff format --check --no-cache $(QUALITY_FILES)
	$(QUALITY) ruff check --no-cache $(QUALITY_FILES)
	$(QUALITY) mypy --cache-dir "$${TMPDIR:-/tmp}/limn-sans-mypy"

hangul: hangul-fonts
	cd $(SITE) && $(RH) tools/build_hangul.py

hangul-measure:
	cd $(SITE) && $(RM) tools/hangul_measure.py --refs --page

pages: refs coverage-page
	cd $(SITE) && set -o pipefail; $(R) tools/build_punct_page.py | tail -1 && $(R) tools/build_weights_page.py | tail -1 && $(R) tools/build_sym_page.py | tail -1

# font files: built from the engine data (play, hangul), not from Quicksand, so a line set with them matches
# the engine's; tools/check_ttf.py then checks every file against that data (coverage, advances, pins, kerning)
fonts:
	cd $(SITE) && $(RF) tools/build_ttf.py && $(RF) tools/check_ttf.py

# Public release: explicit isolated inputs/output; no full Hangul build, no empty ext face.
fonts-release:
	@test -n "$(LIMN_TTF_PLAY_IN)" -a -n "$(LIMN_TTF_SYMBOLS_IN)" -a -n "$(LIMN_TTF_OUT)" -a -n "$(LIMN_TTF_SPACE_PROVENANCE_IN)" || \
	  { echo "Set LIMN_TTF_PLAY_IN, LIMN_TTF_SYMBOLS_IN, LIMN_TTF_SPACE_PROVENANCE_IN and LIMN_TTF_OUT" >&2; exit 1; }
	LIMN_TTF_PROFILE=latin-symbols $(MAKE) fonts

fonts-page:
	cd $(SITE) && uv run --no-project --with playwright python3 tools/check_fonts_page.py

coverage-page: refs
	cd $(SITE) && uv run --no-project --with fonttools --with pillow --with playwright python3 tools/build_coverage_page.py

# app icons: LIMN.icon() drawn by Chromium at the true pixel size (16 20 24 32 are pixel drawings, see icons.html),
# plus the SVGs and the favicons the Limn app vendors (tools/build_icons.py lists every file)
icons:
	cd $(SITE) && uv run --no-project --with playwright --with pillow python3 tools/build_icons.py

# design-system figures: SVG + PNG + manifest.json into OUT (default site/figures, not committed) from limn-brand.js
# and the font files, then checked against the data and scanned for private strings (needs font, play, fonts, refs;
# the app screens run a throwaway Limn instance through uv). Each step execs, so a SIGTERM to make reaches
# the tool, which stops its demo server and removes its temporary folder.
.PHONY: figures
OUT ?= $(SITE)/figures
figures:
	cd $(SITE) && exec uv run --no-project --with playwright --with pillow --with fonttools --with brotli --with uharfbuzz python3 tools/export_figures.py --out $(abspath $(OUT))
	cd $(SITE) && exec uv run --no-project --with playwright --with pillow --with fonttools --with brotli python3 tools/check_figures.py $(abspath $(OUT))

all: play font cuts hangul hangul-measure fonts icons
	$(MAKE) pages

refs:
	bash $(SITE)/tools/fetch_refs.sh

# glyph gates over every weight and cut (tools/audit.py): data, topology, counters, ink, spikes, kerning coverage, accents,
# collisions in real strings, Hangul; fails on any
check:
	cd $(SITE) && $(R) tools/audit.py
	cd $(SITE) && $(RH) tools/audit_hangul.py

preview:
	rsync -a --include /refs/ --include /refs/Quicksand.ttf --include /refs/Nunito.ttf --include /refs/Fredoka.ttf \
	  --include /refs/OFL-Quicksand.txt --include /refs/OFL-Nunito.txt --include /refs/OFL-Fredoka.txt \
	  --exclude '/refs/*' --exclude .glyph-cache/ --exclude tools/__pycache__/ --exclude 'tools/hangul/*.ttf' \
	  --exclude tools/hangul/.params-cache.json --exclude tools/hangul/.params-cache.lock \
	  --exclude 'tools/hangul/.pending-*' "$(SITE)/" "$(PREVIEW)/"
	@# every page there asks for its scripts with a ?v= tag; stamp them all, or browsers keep the data of an older build
	python3 $(SITE)/tools/stamp_preview.py "$(PREVIEW)"

clean:
	cd $(SITE) && rm -f limn-font.js limn-font-play*.js m-width-*.js punct-data.js symbols-data.js weights-data.js weights-seam.js limn-hangul-*.js limn-hangulext-*.js hangul-measure.js && rm -rf fonts icons
