/* limn brand — single source of truth for the final identity (v3, 2026-09-27).
   The typeface is Quicksand Bold with the limn rules applied (tools/build_font.py → limn-font.js):
   spurless n family, the pin for every dot, flat feet on stems that stand on the baseline.
   Every page draws from here. Units are font units (UPM 1000), y down, baseline at 0. */
(function (root) {
  "use strict";
  const F0 = root.LIMN_FONT;

  // kerning with classes: a pair missing from the table falls back to its base pair (é kerns as e)
  const kernOf = (K, KC, a, b) => {
    const v = K[a + b]; if (v !== undefined) return v;
    if (!KC) return 0;
    const l = (KC[a] && KC[a][0]) || a, r = (KC[b] && KC[b][1]) || b;
    return l + r !== a + b ? (K[l + r] || 0) : 0;
  };
  // a character the font does not have is drawn as an open box of cap height, never skipped (proof B05)
  const tofu = (cap, s) => {
    const t = 0.4 * s, A = Math.round(0.6 * cap + 80), a = 40, b = A - 40;
    return { d: `M${a} 0H${b}V${-cap}H${a}Z M${a + t} ${-t}V${-cap + t}H${b - t}V${-t}Z`, adv: A, box: [a, -cap, b, 0], pins: [], tofu: true };
  };

  /* ---------- Hangul (tools/hangul.py → limn-hangul-<w>.js, window.LIMN_HANGUL[w]) ----------
     NanumSquareRound paired with the Latin at each weight. A character the Latin data lacks is taken from
     here; its advance already carries the Hangul tracking. Where a Latin letter meets a Hangul syllable
     (either way) the boundary white H.bnd is added — no pair kerning. The brand 림 stays in the Latin data. */
  const KO = /[ᄀ-ᇿㄱ-ㆎ가-힣]/;
  const isKo = ch => KO.test(ch);
  const isLetter = ch => /\p{L}/u.test(ch);
  // the strong script of a character (null: common, it takes the script of the run it is in)
  const scriptOf = ch => /\p{Script=Latin}/u.test(ch) ? "Latn" : /\p{Script=Greek}/u.test(ch) ? "Grek" : /\p{Script=Hangul}/u.test(ch) ? "Hang" : null;
  const hangulOf = w => (root.LIMN_HANGUL && root.LIMN_HANGUL[w]) || null;
  // the brand drawing (limn-font.js) is Quicksand Bold, S 120; on the HALF curve the family weight nearest it is 700
  // (S 116.8; 800 is 134.7), so the brand's Hangul is 700's. The logo 림 is its own pinned drawing, not this.
  const BRAND_HW = 700;
  const bndOf = (H, prev, ch) => H && prev && isLetter(prev) && isLetter(ch) && isKo(prev) !== isKo(ch) ? (H.bnd || 0) : 0;
  // typographic spaces and zero-width marks (sweep 2026-09-28; tools/build_font.py "spaces", the font files map the
  // same): U+00A0 = the word space, U+2009 U+202F = the parent's thin space, U+2002 U+2003 = en, em, U+3000 = one
  // Hangul syllable (가 of the weight; an em until the Hangul is loaded). A space breaks the kerning like " ";
  // U+00AD U+200B take no room and leave the pair around them kerned. null: not a space.
  const spaceOf = (F, H, ch) => ch === "\u3000" ? (H && H.glyphs["가"] ? H.glyphs["가"].adv : 1000)
    : F.spaces && F.spaces[ch] !== undefined ? F.spaces[ch] : null;
  root.LIMN_isKo = isKo;
  // load limn-hangul-<w>.js for the weights in use (from the directory limn-brand.js came from; works on file://)
  const BASE = (document.currentScript && document.currentScript.src || "").replace(/[^/]*$/, "");
  const loading = {};
  // (→ ← ↑ ↓ are Latin since sym-math 2026-09-29, tools/sym_math.py; ▶ … ☎ are NanumSquareRound's)
  root.LIMN_needsHangul = str => KO.test(str) || /[「」『』〈〉《》【】〔〕、。※〜\u3000・～○●□■△▲☆★▶▷▼▽◀◁◆◇♠♡♥♣♪☎℃㎡㎏㎝㎞①-⑩]/.test(str);
  // limn-hangul-<w>.js carries KS X 1001's 2,350 syllables, the jamo and the punctuation; limn-hangulext-<w>.js the
  // other 8,822 of the 11,172 (tools/build_hangul.py). LIMN_loadHangul(ws, str) loads the extension too when str has a
  // syllable the main file lacks (str === true: always); LIMN_hangulMissing(w, str) says whether it is still needed.
  const loadingX = {};
  const script = (src, warn) => new Promise(res => {
    const s = document.createElement("script");
    s.src = src; s.charset = "utf-8";
    s.onload = () => res(true);
    s.onerror = () => { console.warn(warn); res(false); };
    document.head.appendChild(s);
  });
  const hangulMissing = (w, str) => {
    const H = hangulOf(w);
    if (!H) return !!str;                        // the main file first (callers ask only when LIMN_needsHangul)
    if (!str || !H.ext || H.extLoaded) return false;
    if (str === true) return true;
    for (const ch of str) if (ch >= "가" && ch <= "힣" && !H.glyphs[ch]) return true;
    return false;
  };
  root.LIMN_hangulMissing = hangulMissing;
  root.LIMN_loadHangul = function (ws, str) {
    return Promise.all([].concat(ws).map(w => {
      if (!hangulOf(w) && !loading[w]) loading[w] = script(`${BASE}limn-hangul-${w}.js`, `limn: limn-hangul-${w}.js missing (make hangul) — Hangul shows as tofu`);
      return (hangulOf(w) ? Promise.resolve(true) : loading[w]).then(ok => {
        const H = hangulOf(w);
        if (!ok || !H || !hangulMissing(w, str)) return ok;
        if (!loadingX[w]) loadingX[w] = script(`${BASE}${H.ext}`, `limn: ${H.ext} missing (make hangul) — syllables outside KS X 1001 show as tofu`).then(okx => {
          const X = root.LIMN_HANGUL_EXT && root.LIMN_HANGUL_EXT[w];
          if (okx && X) { Object.assign(H.glyphs, X.glyphs); H.extLoaded = true; }
          return ok;
        });
        return loadingX[w];
      });
    }));
  };
  function make(OVR = {}) {
    const P = {
      height: "asc",  // asc: pin top on the ascender (final) · centre: pin centre on the l top · compact: older rule, short extenders
      gd: 0.4,        // white gap between pin and i stem, in stems
      track: 0,       // extra space after every glyph (font units)
      feet: "flat",   // flat (final) · round: Quicksand as it is (for the don'ts)
      ...OVR,
    };
    const V = P.height === "compact" ? F0.variants.compact : null;
    const s = F0.s, XH = F0.xh, XO = F0.xo, CAP = F0.cap;
    const ASC = V ? V.asc : F0.asc, DESC = V ? V.desc : F0.desc;
    const r = F0.pin.r;
    const pinCY = gd => -(XH + gd * s + r);             // i pin centre for a gap (y down)
    const cyOf = gd => P.height === "centre" ? -ASC : pinCY(gd);
    const CY = cyOf(P.gd);
    const glyph = ch => {
      const g = (V && V.glyphs[ch]) || F0.glyphs[ch];
      if (g && P.feet === "round" && g.orig) return { ...g, d: g.orig.d, adv: g.orig.adv };
      if (!g) { const H = hangulOf(BRAND_HW); return H && H.glyphs[ch]; }   // the brand weight's Hangul
      return g;
    };
    const PINNED = new Set(["i", "j"]);                  // pins that follow the i rule (림 keeps its own, smaller pin)

    const COLOR = {
      ink: "#15161a",   // 먹 — strokes
      ver: "#e8452c",   // 주 — the pin, and only the pin
      paper: "#fbfaf7", // 종이 — light ground
      bone: "#fbf1e6",  // 뼈종이 — app-icon ground
      cream: "#f4ede1", // 미색 — strokes on the ink ground
      muted: "#6d6a64",
      teal: "#0f3a40", amber: "#ffc24b", blue: "#2f5bea", sky: "#fff3e6", // expression pairs
    };
    const f = n => +(+n).toFixed(1);

    /* ---------- typesetting ----------
       o: {ink, pin, gd, anim ("w" write once · "wl" write loop), step, gattr(ch, x, i), full, pad, track} */
    function typeset(str, o = {}) {
      // pins are ink by default; vermilion only where limn itself speaks — the app (o.app) and the
      // wordmark/icon (user 2026-09-27: "점을 빨간색으로 하는 거는 limn 앱에 사용할 경우고 일반적으로는 꺼줘")
      const ink = o.ink ?? COLOR.ink, pin = o.pin ?? (o.app ? COLOR.ver : ink), gd = o.gd ?? P.gd, cy = cyOf(gd);
      const step = o.step ?? 0.08, track = o.track ?? P.track;
      let x = 0, prev = null, html = "", n = 0, top = Infinity, bot = -Infinity, left = Infinity, right = -Infinity;
      const glyphs = [], dots = [];
      for (const ch of str) {
        if (ch === " ") { x += F0.space + track; prev = null; continue; }
        const sp = spaceOf(F0, hangulOf(BRAND_HW), ch);
        if (sp !== null) { if (sp) { x += sp + track; prev = null; } continue; }
        const HK = ch === "림" && o.rim !== "logo" && hangulOf(BRAND_HW);   // 림 in text: the plain syllable, no pin
        const g = (HK && HK.glyphs[ch]) || glyph(ch) || tofu(CAP, s);
        if (prev) x += kernOf(F0.kern, F0.kcls, prev, ch) + ((o.xkern || {})[prev + ch] || 0) + bndOf(hangulOf(BRAND_HW), prev, ch);
        // pin clearance is in the kerning: build_font.py measures the pin against each neighbour's
        // outline (both sides) and widens pairs closer than 0.54 s (F.pinkern)
        const anim = o.anim ? ` class="gl" style="animation-delay:${(n * step).toFixed(2)}s"` : "";
        const ga = o.gattr ? o.gattr(ch, x, glyphs.length) : "";
        const inner = g.d ? `<path${anim} d="${g.d}"/>` : "";
        if (inner) html += `<g transform="translate(${f(x)} 0)">${ga ? `<g ${ga}>${inner}</g>` : inner}</g>`;
        let [x0, y0, x1, y1] = g.box;
        for (const [px, py] of g.pins || []) {
          const y = PINNED.has(ch) ? cy : py, pr = g.pinr || r;
          dots.push([x + px, y, pr]); y0 = Math.min(y0, y - pr);
        }
        left = Math.min(left, x + x0); right = Math.max(right, x + x1); top = Math.min(top, y0); bot = Math.max(bot, y1);
        glyphs.push({ ch, x, adv: g.adv, box: g.box, stems: g.stems || [] });
        x += g.adv + track; prev = ch; n++;
      }
      if (!glyphs.length) { left = right = 0; top = -XH; bot = 0; }
      if (o.full) { top = Math.min(top, -ASC, cy - r); bot = Math.max(bot, -DESC); }
      const pad = o.pad ?? 0, end = n * step;
      const dotsHtml = dots.map(([cx, cy2, pr = r], i) => `<circle${o.anim ? ` class="pt" style="animation-delay:${(end + 0.1 + i * 0.07).toFixed(2)}s"` : ""} cx="${f(cx)}" cy="${f(cy2)}" r="${f(pr)}" fill="${pin}"/>`).join("");
      return {
        body: `<g fill="${ink}">${html}</g>${dotsHtml}`,
        vb: [left - pad, top - pad, right - left + 2 * pad, bot - top + 2 * pad], glyphs, dots, end: end + 0.5,
      };
    }
    const vbs = v => v.map(f).join(" ");
    function svg(t, o = {}) {
      const [, , w, h] = t.vb, k = o.scale ?? (o.h / h);
      return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vbs(t.vb)}" width="${f(w * k)}" height="${f(h * k)}"${o.attrs ? " " + o.attrs : ""}>${o.extra || ""}${t.body}</svg>`;
    }
    const atXH = px => px / XH;                          // scale for a given x-height in px

    /* optical sizes: below ~24 px tall the pin gap opens so pin and stem do not fuse */
    // optical size, one rule for every page and the playground: on screen the white under the pin
    // never drops below 1.25 px (px = the wordmark's height, baseline to pin top). At P.gd the pin top is the
    // ascender (ASC); a wider gap raises it by the difference, and the height with it, so the gap is solved on
    // that height, rounded up (2026-10-01: solved on ASC alone it left 1.2 px at 12 px and 1.23 px at 16 px)
    const gdFor = px => {
      const g = 1.25 * (ASC - P.gd * s) / (s * (px - 1.25));
      return g <= P.gd ? +P.gd.toFixed(2) : Math.ceil(g * 100) / 100;
    };

    /* the wordmark is the typeface with a logo kerning: the three letter gaps of "limn" are set to
       the same optical white as l|i (area model calibrated on Quicksand's own nn = oo; spacing audit
       2026-09-27: l|i 134.4 · i|m 127.4 · m|n 143.9 → kern = E(l|i) − E(pair), |k| < 5 dropped) */
    const LOGO_KERN = { li: -7, im: -6, mn: -10 };   // 2026-09-27 class spacing (Tracy) widened l i m n; these keep the wordmark's ink exactly where it was
    const wordmark = (o = {}) => typeset("limn", { xkern: LOGO_KERN, pin: COLOR.ver, ...o });
    const rim = (o = {}) => typeset("림", { pin: COLOR.ver, rim: "logo", ...o });

    /* the minim: a stem of x-height with a round top and a flat foot, the shape of i without its pin */
    const minimPath = (x, w = s, h = XH) => `M${f(x - w / 2)} 0V${f(-h + w / 2)}A${f(w / 2)} ${f(w / 2)} 0 0 1 ${f(x + w / 2)} ${f(-h + w / 2)}V0Z`;

    /* ---------- app icon: the i, on the Apple 1024 grid ---------- */
    function sqPath(x0 = 100, y0 = 100, w = 824, n = 5, steps = 96) {
      const a = w / 2, cx = x0 + a, cy = y0 + a; let d = "";
      for (let i = 0; i <= steps; i++) {
        const t = i / steps * 2 * Math.PI, c = Math.cos(t), sn = Math.sin(t);
        d += (i ? "L" : "M") + (cx + a * Math.sign(c) * Math.pow(Math.abs(c), 2 / n)).toFixed(1) + " " + (cy + a * Math.sign(sn) * Math.pow(Math.abs(sn), 2 / n)).toFixed(1);
      }
      return d + "Z";
    }
    const SQ = sqPath();
    // theme: light (bone ground, ink stem) | dark (ink ground, cream stem) | ver (vermilion ground, cream stem & pin)
    const iconColors = th => ({
      bg: { light: COLOR.bone, dark: COLOR.ink, ver: COLOR.ver }[th],
      stem: { light: COLOR.ink, dark: COLOR.cream, ver: COLOR.sky }[th],
      pin: th === "ver" ? COLOR.sky : COLOR.ver,
    });
    const iconSpec = px => px <= 20 ? { w: 1.45 * s, gd: 0.75 } : px <= 40 ? { w: 1.2 * s, gd: 0.55 } : { w: s, gd: P.gd };

    /* ---------- app icon at 16 · 20 · 24 · 32 px: drawn on the pixel grid (2026-09-29, site/icons.html) ----------
       Scaled down, the 1024 drawing puts every edge between pixels and the stem, foot and pin blur. At these
       sizes each icon is its own drawing in whole pixels of that size (y down). Every straight edge sits on a
       pixel boundary; antialiasing is only where it was drawn by hand: the squircle corners, the pin's rim at
       24/32 and the round top of the 32 stem.
         body [x, w, corner]  a w×w square at (x, x); corner = alphas of the top-left pixels, row by row until
                              the edge is solid (the other corners mirror it). Apple's 824/1024 → the nearest
                              whole size; corner ≈ a circle of radius w/4, the pixel profile of the squircle
         stem [x, w, top, base, cap]  whole pixels; cap = alphas of the top row (round top), none = flat
         pin  [x, y, rows]    alphas per pixel
       Common rules: the stem is centred on the body's axis (even canvas → even stem; the 32 stem is 3 px, so
       its body is 25, odd, and the body sits 0.5 px up-left in the canvas instead of the stem sitting 0.5 px
       off-axis in the body); one full row of ground between pin and stem; the i is 0.63–0.65 of the body
       (the large one 0.57): the stem is heavier than the large stroke and a straight scale reads stubby, so
       16, 24 and 32 get one pixel more stem than the straight scale (20's rounding already gives it); where
       the i's height and the body's differ in parity the i sits 0.5 px high. 16/20: the pin is a solid 2×2 (a
       1.7–1.9 px pin at scale; its rim antialiased would only turn it pink); 24/32: a disc (⌀3, ⌀4) whose
       rim is its coverage. */
    const ICON_PX = {
      16: { n: 16, body: [1, 14, [[0, .35, .84], [.35], [.84]]], stem: [7, 2, 6, 12], pin: [7, 3, [[1, 1], [1, 1]]] },
      20: { n: 20, body: [2, 16, [[0, .16, .69], [.16], [.69]]], stem: [9, 2, 8, 15], pin: [9, 5, [[1, 1], [1, 1]]] },
      24: { n: 24, body: [2, 20, [[0, 0, .32, .76], [0, .55], [.32], [.76]]], stem: [11, 2, 9, 18],
            pin: [10, 5, [[.15, .9, .9, .15], [.5, 1, 1, .5], [.15, .9, .9, .15]]] },
      32: { n: 32, body: [3, 25, [[0, 0, 0, .45, .8], [0, 0, .83], [0, .83], [.45], [.8]]], stem: [14, 3, 12, 23, [.5, 1, .5]],
            pin: [13, 7, [[0, .7, 1, .7, 0], [.4, 1, 1, 1, .4], [.4, 1, 1, 1, .4], [0, .7, 1, .7, 0]]] },
    };
    // pixels [x, y, alpha] → one path per alpha (solid pixels merge into row runs)
    function pxPaths(cells, fill) {
      const by = new Map();
      for (const [x, y, a] of cells) if (a > 0) { if (!by.has(a)) by.set(a, []); by.get(a).push([x, y]); }
      let out = "";
      for (const [a, ps] of by) {
        ps.sort((p, q) => p[1] - q[1] || p[0] - q[0]);
        let d = "";
        for (let i = 0; i < ps.length;) {
          const [x, y] = ps[i]; let n = 1;
          while (i + n < ps.length && ps[i + n][1] === y && ps[i + n][0] === x + n) n++;
          d += `M${x} ${y}h${n}v1h${-n}z`; i += n;
        }
        out += `<path d="${d}" fill="${fill}"${a < 1 ? ` fill-opacity="${a}"` : ""}/>`;
      }
      return out;
    }
    // shape-rendering crispEdges on the whole drawing: it is made of whole-pixel squares only, so at 1:1 it
    // renders the same as with antialiasing, and if the svg lands on a fractional device pixel every square
    // snaps by the same rule — the drawing moves as a whole instead of smearing over two pixel columns.
    // No drop shadow: at these sizes it is 0.2–0.4 px and would only soften the foot of the body.
    function iconPixels(D, px = D.n, o = {}) {
      const c = iconColors(o.theme || "light");
      const [bx, bw, corner] = D.body, [sx, sw, st, sb, cap] = D.stem, [qx, qy, rows] = D.pin;
      const ca = (i, j) => { const row = corner[Math.min(j, bw - 1 - j)], k = Math.min(i, bw - 1 - i); return row && k < row.length ? row[k] : 1; };
      const body = [], stem = [], pin = [];
      for (let j = 0; j < bw; j++) for (let i = 0; i < bw; i++) body.push([bx + i, bx + j, ca(i, j)]);
      for (let y = st; y < sb; y++) for (let i = 0; i < sw; i++) stem.push([sx + i, y, cap && y === st ? cap[i] : 1]);
      rows.forEach((row, j) => row.forEach((a, i) => pin.push([qx + i, qy + j, a])));
      const pinSvg = pxPaths(pin, c.pin);
      return `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 ${D.n} ${D.n}" shape-rendering="crispEdges" role="img" aria-label="limn">`
        + pxPaths(body, c.bg) + pxPaths(stem, c.stem) + (o.dotClass ? `<g class="${o.dotClass}">${pinSvg}</g>` : pinSvg) + "</svg>";
    }

    /* icon(px): px in CSS pixels. When px × devicePixelRatio (o.dpr overrides it) is 16, 20, 24 or 32 the pixel
       drawing of that device size is used, so icon(16) on a 2× screen is the 32 drawing; any other size, or
       o.vector, is the 1024 drawing scaled (iconSpec thickens it below 40 px).
       o.bleed: the body fills the whole square, no squircle and no margin (an iOS home-screen icon: iOS cuts its own
       corners and shows transparent ones as black). The i keeps its size relative to the body, so the viewBox is the
       squircle's box, 100 100 824 824; the optical size is that of the squircle icon with the same body
       (px × 1024 / 824). Always the vector drawing, never a shadow. */
    function icon(px, o = {}) {
      const dev = +(px * (o.dpr ?? root.devicePixelRatio ?? 1)).toFixed(2);
      if (!o.vector && !o.bleed && ICON_PX[dev]) return iconPixels(ICON_PX[dev], px, o);
      const { bg, stem, pin } = iconColors(o.theme || "light");
      const { w, gd } = iconSpec(o.bleed ? px * 1024 / 824 : px), rr = r * w / s;
      const cy = -(XH + gd * w + rr), top = cy - rr;
      const k = 470 / -top, id = "is" + Math.random().toString(36).slice(2, 7);
      const flat = o.flat || o.bleed;
      const shadow = flat ? "" : `<defs><filter id="${id}" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="12" stdDeviation="14" flood-opacity=".22"/></filter></defs>`;
      const body = o.bleed ? `<rect x="100" y="100" width="824" height="824" fill="${bg}"/>` : `<path d="${SQ}" fill="${bg}"${flat ? "" : ` filter="url(#${id})"`}/>`;
      return `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="${o.bleed ? "100 100 824 824" : "0 0 1024 1024"}" role="img" aria-label="limn">${shadow}${body}
      <g transform="translate(512 512) scale(${k.toFixed(4)}) translate(0 ${f(-top / 2)})"><path d="${minimPath(0, w)}" fill="${stem}"/><circle ${o.dotClass ? `class="${o.dotClass}" ` : ""}cx="0" cy="${f(cy)}" r="${f(rr)}" fill="${pin}"/></g></svg>`;
    }

    /* ---------- browser favicon: 16 · 32 px pixel drawings on 먹 (2026-09-30, site/icons.html) ----------
       The tab favicon is its own drawing, not the app icon. A tab is 16 CSS px and Chrome's light tab is nearly
       뼈종이 (ΔE ≈ 8), so on a light tab the squircle tile vanishes and only the 2 × 9 px i reads. The favicon is
       one drawing for light and dark tabs: a 먹 rounded square filling the whole square (A16's corner profile,
       r 3.5 at 16 and 7 at 32), a 미색 stem and the 주 pin; the i is 10 of 16 (20 of 32) px tall. Same format and
       rules as ICON_PX, drawn by iconPixels on the dark ground: straight edges on pixel boundaries, stem columns
       solid (the 32's top row is its round cap), one row (two at 32) of ground between pin and stem. */
    const FAVICON_PX = {
      16: { n: 16, body: [0, 16, [[0, .35, .84], [.35], [.84]]], stem: [7, 2, 6, 13], pin: [7, 3, [[1, 1], [1, 1]]] },
      32: { n: 32, body: [0, 32, [[0, 0, 0, 0, .53, .83], [0, 0, .35], [0, .35], [0], [.53], [.83]]], stem: [14, 4, 13, 26, [.3, 1, 1, .3]],
            pin: [13, 6, [[0, .47, .93, .93, .47, 0], [.27, 1, 1, 1, 1, .27], [.48, 1, 1, 1, 1, .48], [.27, 1, 1, 1, 1, .27], [0, .47, .93, .93, .47, 0]]] },
    };
    /* favicon(px): px in CSS pixels, drawn at px × devicePixelRatio device pixels (o.dpr overrides it): the 16 or 32
       drawing of that size; any other size takes the 32 drawing, scaled. Always 먹; o.dotClass as in iconPixels. */
    function favicon(px, o = {}) {
      const dev = +(px * (o.dpr ?? root.devicePixelRatio ?? 1)).toFixed(2);
      return iconPixels(FAVICON_PX[dev] || FAVICON_PX[32], px, { ...o, theme: "dark" });
    }

    /* ---------- measurement helpers ---------- */
    function lum(hex) {
      const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
      return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    }
    const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };

    // stems of "limn" as set: l, i, m×3, n×2 (x centres) — for the minim animation and the BI drawing
    const MINIM = (() => {
      const t = wordmark(), xs = [];
      for (const g of t.glyphs) for (const sx of g.stems) xs.push(f(g.x + sx));
      return { stems: xs, l: xs[0], dotX: xs[1], glyphs: t.glyphs, legs: xs.slice(2) };
    })();

    /* the minim story ("점이 떨어지면 읽힌다"): seven stems stand; the pin drops on the second; l
       rises to the ascender; the m·n arches sweep in over their stems. The last frame is the
       wordmark itself — every shape in it is the typeface's own outline.
       o: {h, ink, pin, anim, stage: "stems" (the seven stems only, still)} */
    function minimArt(o = {}) {
      const ink = o.ink ?? COLOR.ink, pin = o.pin ?? COLOR.ver, pad = o.pad ?? 40;
      const t = wordmark({ ink, pin, pad }), wrap = inner => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vbs(t.vb)}" width="${f(o.h * t.vb[2] / t.vb[3])}" height="${o.h}">${inner}</svg>`;
      const M = MINIM;
      if (o.stage === "stems") return wrap(`<g fill="${ink}">${M.stems.map(x => `<path d="${minimPath(x)}"/>`).join("")}</g>`);
      if (!o.anim) return svg(t, { h: o.h });
      const dl = x => Math.abs(x - M.dotX) / 260 * 0.07;
      let a = `<g fill="${ink}"><path d="${minimPath(M.l)}"/><path class="mn-asc" style="animation-delay:${dl(M.l).toFixed(2)}s" d="${minimPath(M.l)}"/><path d="${minimPath(M.dotX)}"/>`;
      for (const g of M.glyphs.slice(2)) {
        const [bx0, , bx1] = g.box, t0 = dl(g.x + (bx0 + bx1) / 2) - 0.15;
        // the arch front sweeps the glyph box linearly (0.6 s, from 0 to 105 %); a stem's minim goes
        // when the front reaches the stem's centre, so no round top is left standing above an arch
        for (const sx of g.stems) a += `<path class="mn-leg" style="animation-delay:${(t0 + 0.6 * (sx - bx0) / (bx1 - bx0) / 1.05 - 0.03).toFixed(3)}s" d="${minimPath(g.x + sx)}"/>`;
        a += `<g transform="translate(${f(g.x)} 0)"><path class="mn-gl" style="animation-delay:${t0.toFixed(2)}s" d="${glyph(g.ch).d}"/></g>`;
      }
      return wrap(a + `</g><circle class="mn-dot" cx="${M.dotX}" cy="${f(CY)}" r="${f(r)}" fill="${pin}"/>`);
    }

    return {
      P, F: F0, s, XH, XO, ASC, DESC, CAP, r, CY, pinCY, COLOR, glyph, f, LOGO_KERN,
      typeset, svg, vbs, atXH, gdFor, wordmark, rim, minimPath, minimArt, icon, iconSpec, iconPixels, ICON_PX, favicon, FAVICON_PX, SQ, sqPath, contrast, MINIM,
    };
  }
  root.LIMN_make = make;
  root.LIMN = make(root.LIMN_OVERRIDES || {});

  /* ---------- playground: every limn rule as a switch (type page, "직접 써보기") ----------
     Needs limn-font-play.js (tools/build_play.py): the rules applied at wght 100–900 (Quicksand 300–700, tools/weights.py outside), plus
     round feet, Quicksand's own n family and the original dots, so each rule can be turned off.
     c: {w, spur (Quicksand n family), feet ("flat"|"round"), dots ("pin"|"orig"), fit (pin by the
         rule) or gap (s) and dia (s), optical + ppu (optical size), track, kern, ss01 (double-storey a g),
         zero (dotted 0), tnum (false: proportional figures; tabular is the default), ink, pin, anim, step, full, pad} */
  root.LIMN_playset = function (str, c = {}) {
    let W = root.LIMN_PLAY[c.w || 700];
    // text cuts (proof audit 2026-09-27, C-05): when the optical size would have to enlarge the pin or
    // open its gap, take the weight built at the nearest design size (tools/build_play.py with
    // LIMN_OPT_PX), where commas, quotes, … ! ? and the kerning are built around the larger pin. The
    // per-pin minimum below still applies between two cuts.
    if (c.optical && c.ppu && root.LIMN_PLAY_OPT && (c.fit ?? true) && c.dots !== "orig") {
      const px = c.ppu * 1000;
      if (W.pin.gap * c.ppu < 1.25 || 2 * W.pin.r * c.ppu < 2.2) {
        const cuts = Object.keys(root.LIMN_PLAY_OPT).map(Number).sort((a, b) => a - b);
        const cut = cuts.reduce((b, p) => Math.abs(Math.log(p / px)) < Math.abs(Math.log(b / px)) ? p : b, cuts[0]);
        W = root.LIMN_PLAY_OPT[cut][c.w || 700] || W;
      }
    }
    const s = W.s, f = n => +(+n).toFixed(1);
    // pin: "rule" follows Quicksand's own dot at this weight (× 1.246, gap × 0.738 — at 700 the pin
    // top lands on the ascender); "free" takes gap and diameter in stems. Optical size: below a few
    // pixels the gap and the pin are held at a minimum on screen (ppu = pixels per font unit).
    const fit = c.fit ?? true;
    let gap = fit ? W.pin.gap : (c.gap ?? 0.4) * s;
    let r = c.dots === "orig" ? null : fit ? W.pin.r : (c.dia ?? 1.31) * s / 2;
    const opt = { gap: false, r: false };
    if (c.optical && c.ppu) {
      if (gap * c.ppu < 1.25) { gap = 1.25 / c.ppu; opt.gap = true; }
      if (r && 2 * r * c.ppu < 2.2) { r = 1.1 / c.ppu; opt.r = true; }
    }
    const ink = c.ink ?? "#15161a", pinC = c.dots === "orig" || !c.app ? ink : (c.pin ?? "#e8452c");   // vermilion only in app mode
    const step = c.step ?? 0.06, track = c.track ?? 0, kern = c.kern ?? true;
    const HG = hangulOf(c.w || 700);
    const glyph = ch => {
      if ((c.ss01 && "ag".includes(ch)) || (c.zero && ch === "0")) return W.alt[ch];
      if (c.tnum === false && W.pglyph && W.pglyph[ch]) return W.pglyph[ch];
      if (ch === "림" && c.rim !== "logo" && HG && HG.glyphs[ch]) return HG.glyphs[ch];   // 림 in text is the plain syllable; the pinned 림 is the logo (rim:"logo")
      const g = W.glyphs[ch]; if (!g) return (HG && HG.glyphs[ch]) || null;
      if (c.spur && W.spur[ch]) return c.feet === "round" ? W.spur[ch] : { ...W.spur[ch], ...W.spurfeet[ch] };
      if (c.feet === "round" && W.nofeet[ch]) return { ...g, ...W.nofeet[ch] };
      return g;
    };
    // pins of a glyph for the current rule: [x, y (down), radius]
    const pinsOf = (ch, g) => {
      if (ch === "림") return g.pinx === undefined ? [] : g.pinr ? [[g.pinx, g.piny, g.pinr]] : r ? [[g.pinx, -(W.xh + gap + r), r]] : [];   // 림's pin: its own ㅣ width
      const d = W.dots[ch]; if (!d) return [];
      return d.pins.map(([k, x, y, r0]) => {
        if (!r) return [x, -(y - (k === "mid" ? 0 : r0)), r0];               // Quicksand's own dot
        const nx = d.only ? x + (r - r0) : x;
        const os = W.xo - W.xh;   // pins overshoot like o: below the baseline, above the x-height
        const cy = k === "i" ? W.xh + gap + r : k === "base" ? r - os : k === "top" ? W.xo - r : y;
        return [nx, -cy, r];
      });
    };
    const advOf = (ch, g) => { const d = W.dots[ch]; return d && d.only ? d.adv0 + (r ? 2 * (r - d.pins[0][3]) : 0) : g.adv; };
    // browsers split a line into script runs and kern inside a run only, so a pair across a strong script boundary
    // (Latin | Greek: "Tο") is not kerned; figures, punctuation and symbols belong to the run they are in
    let run = null;
    let x = 0, prev = null, n = 0, html = "", top = Infinity, bot = -Infinity, left = Infinity, right = -Infinity;
    const glyphs = [], dots = [];
    for (const ch of str) {
      if (ch === " ") { x += W.space + track; prev = null; continue; }
      const sp = spaceOf(W, HG, ch);
      if (sp !== null) { if (sp) { x += sp + track; prev = null; } continue; }
      const g = glyph(ch) || tofu(W.cap, s);
      const pn = (c.tnum === false && !(W.pglyph && W.pglyph[ch]) && W.pnum && W.pnum[ch]) || null;   // figures are tabular; "pnum" gives back the proportional widths
      const sc = scriptOf(ch), cross = !!(run && sc && sc !== run);
      if (sc) run = sc;
      if (prev && kern && !cross) x += (c.tnum === false && W.pkern && (prev + ch) in W.pkern ? W.pkern[prev + ch] : kernOf(W.kern, W.kcls, prev, ch)) || 0;
      if (prev) x += bndOf(HG, prev, ch);                   // Latin | Hangul white (not kerning: always on)
      const ps = pinsOf(ch, g);   // pin clearance comes with the kerning (measured at this weight's own pin)
      const off = pn ? -pn[1] : 0;
      const anim = c.anim ? ` class="gl" style="animation-delay:${(n * step).toFixed(2)}s"` : "";
      if (g.d) html += `<g transform="translate(${f(x + off)} 0)"><path${anim} d="${g.d}"/></g>`;
      let [x0, y0, x1, y1] = g.box; x0 += off; x1 += off;
      if (!g.d) { x0 = Infinity; y0 = Infinity; x1 = -Infinity; y1 = -Infinity; }
      for (const [px, py, pr] of ps) { dots.push([x + px, py, pr]); x0 = Math.min(x0, px - pr); x1 = Math.max(x1, px + pr); y0 = Math.min(y0, py - pr); y1 = Math.max(y1, py + pr); }
      left = Math.min(left, x + x0); right = Math.max(right, x + x1); top = Math.min(top, y0); bot = Math.max(bot, y1);
      glyphs.push({ ch, x, box: [x0, y0, x1, y1] });
      x += (pn ? pn[0] : advOf(ch, g)) + track; prev = ch; n++;
    }
    if (!glyphs.length) { left = right = 0; top = -W.xh; bot = 0; }
    if (c.full) { top = Math.min(top, -W.asc); bot = Math.max(bot, -W.desc); }
    const pad = c.pad ?? 0, end = n * step;
    const dotsHtml = dots.map(([cx, cy, pr], i) => `<circle${c.anim ? ` class="pt" style="animation-delay:${(end + 0.1 + i * 0.07).toFixed(2)}s"` : ""} cx="${f(cx)}" cy="${f(cy)}" r="${f(pr)}" fill="${pinC}"/>`).join("");
    return {
      body: `<g fill="${ink}">${html}</g>${dotsHtml}`, vb: [left - pad, top - pad, right - left + 2 * pad, bot - top + 2 * pad],
      glyphs, dots, info: { w: W.w, s, xh: W.xh, asc: W.asc, desc: W.desc, r, gap, pinTop: r ? W.xh + gap + 2 * r : null, opt, qr: W.pin.qr },
    };
  };
})(window);
