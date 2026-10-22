// Page 4, Color: tokens, "vermilion is for the pin", contrast, ground and text in Light and Dark.
const wset = await lib('wordmarkSet', 'Logo/Wordmark'), iset = await lib('iconSet', 'Icon/App');
const tile = nm => { const c = wset.children.find(x => x.name === nm); if (!c) throw new Error('no wordmark variant ' + nm); return c.createInstance(); };
const icon = (size, theme) => { const c = iset.children.find(x => x.name === `size=${size}, theme=${theme}`); if (!c) throw new Error('no icon variant ' + size + ' ' + theme); return c.createInstance(); };
const NAME = Object.fromEntries(D.tokens.map(t => [t[0], t[1]]));
const needText = D.contrast.find(c => c[3] === 'text')[4], needGfx = D.contrast.find(c => c[3] !== 'text')[4];
const { P, secs } = await shell(D.need);

// 1 Tokens
const s1 = await sect(secs, 'Tokens', 'Six brand tokens, one value each in Light and Dark. Each is a variable in the Library.');
const r1 = fr(s1, 'Token row', 'HORIZONTAL', { g: 'space/24' }); r1.layoutSizingHorizontal = 'FILL';
for (const [key, nm, hex, use] of D.tokens) {
  const c = fr(r1, 'Token/' + nm, 'VERTICAL', { g: 'space/8' }); c.layoutSizingHorizontal = 'FILL';
  const chip = shape(c, 'rect', 'Swatch', 100, 120); chip.cornerRadius = 8; fill(chip, key); stroke(chip, 'ink', 0.08); chip.layoutSizingHorizontal = 'FILL'; chip.layoutSizingVertical = 'FIXED';
  await tx(c, nm, 'Heading/3', { w: 'fill', name: 'Name' });
  await tx(c, hex, 'Mono', { w: 'fill', name: 'Hex' });
  await tx(c, 'Variable ' + key, 'Mono', { w: 'fill', fill: 'muted', name: 'Variable' });
  await tx(c, use, 'Body/S', { w: 'fill', fill: 'muted', name: 'Use' });
}

// 2 Vermilion is for the pin
const s2 = await sect(secs, 'Vermilion is for the pin', 'Vermilion appears only on the pin: the dot over the i in the wordmark and in the app icon. Strokes, text and grounds never use it.');
const r2 = fr(s2, 'Pin row', 'HORIZONTAL', { g: 'space/24' }); r2.layoutSizingHorizontal = 'FILL';
const { a: p1 } = await fcard(r2, { name: 'Wordmark', title: 'Wordmark', cap: D.wordmarkCap, pad: 0, minH: 200, ground: 'paper' }); p1.appendChild(tile('theme=light, ground=tile'));
const { a: p2 } = await fcard(r2, { name: 'App icon', title: 'App icon', cap: 'The pin is the only vermilion in the icon, on the bone and the ink squircle alike.', pad: 'space/32', minH: 200 });
p2.layoutMode = 'HORIZONTAL'; p2.layoutSizingHorizontal = 'FILL'; p2.primaryAxisAlignItems = 'CENTER'; p2.counterAxisAlignItems = 'CENTER'; p2.itemSpacing = 24; p2.appendChild(icon('64', 'light')); p2.appendChild(icon('64', 'dark'));
const { a: p3 } = await fcard(r2, { name: 'Not vermilion', title: 'Not for strokes', cap: D.strokeCap, pad: 'space/32', minH: 200 });
fig(p3, 'color-misuse-stroke-ver', {});

// 3 Contrast
const s3 = await sect(secs, 'Contrast', 'WCAG contrast for the pairs the system uses. Text needs ' + needText + ':1; graphics and icon strokes need ' + needGfx + ':1.');
const tbl = fr(s3, 'Contrast table', 'VERTICAL'); tbl.layoutSizingHorizontal = 'FILL';
const cols = [{ w: 72 }, { w: 'fill' }, { w: 'fill' }, { w: 'fill' }, { w: 96 }, { w: 96 }, { w: 72 }];
const hr = fr(tbl, 'Header', 'HORIZONTAL', { g: 'space/24', pt: 'space/12', pb: 'space/12' }); hr.layoutSizingHorizontal = 'FILL'; hair(hr, 'Bottom', 0.25);
for (const [i, h] of ['Preview', 'Foreground', 'Ground', 'Use', 'Ratio', 'Needs', 'Result'].entries()) await tx(hr, h, 'Caption', { w: cols[i].w, fill: 'muted', name: 'Head' });
for (const [fg, bg, ratio, use, need, pass] of D.contrast) {
  const row = fr(tbl, 'Row ' + NAME[fg] + ' on ' + NAME[bg], 'HORIZONTAL', { g: 'space/24', pt: 'space/12', pb: 'space/12' }); row.layoutSizingHorizontal = 'FILL'; row.counterAxisAlignItems = 'CENTER'; hair(row, 'Bottom');
  const pv = fr(row, 'Preview', 'HORIZONTAL'); pv.resize(72, 40); pv.primaryAxisAlignItems = 'CENTER'; pv.counterAxisAlignItems = 'CENTER'; pv.cornerRadius = 6; fill(pv, bg); stroke(pv, 'ink', 0.12);
  if (use === 'text') await tx(pv, 'Aa', 'Heading/3', { w: 40, fill: fg, align: 'CENTER', name: 'Sample' });
  else if (use === 'icon stroke') { const b = shape(pv, 'rect', 'Stroke sample', 4, 20); b.cornerRadius = 2; fill(b, fg); }
  else { const e = shape(pv, 'ellipse', 'Pin sample', 16, 16); fill(e, fg); }
  await tx(row, NAME[fg], 'Body/S', { w: 'fill', name: 'Foreground' });
  await tx(row, NAME[bg], 'Body/S', { w: 'fill', name: 'Ground' });
  await tx(row, use.charAt(0).toUpperCase() + use.slice(1), 'Body/S', { w: 'fill', fill: 'muted', name: 'Use' });
  await tx(row, ratio + ':1', 'Mono', { w: 96, name: 'Ratio' });
  await tx(row, need + ':1', 'Mono', { w: 96, fill: 'muted', name: 'Needs' });
  await tx(row, pass ? 'Pass' : 'Fail', 'Body/S', { w: 72, name: 'Result' });
}

// 4 Ground and text
const s4 = await sect(secs, 'Ground and text', 'Two modes, one rule: the pin stays vermilion in both.');
const r4 = fr(s4, 'Mode row', 'HORIZONTAL', { g: 'space/24' }); r4.layoutSizingHorizontal = 'FILL';
const coll = await N.variables.getVariableCollectionByIdAsync(CFG.lib.colorCollection);
if (!coll || coll.name !== 'Color') throw new Error('no Color collection ' + CFG.lib.colorCollection);
const modeId = nm => { const m = coll.modes.find(x => x.name === nm); if (!m) throw new Error('no mode ' + nm); return m.modeId; };
for (const [mode, tnm, rows] of [['Light', 'theme=light, ground=tile', [['bg', 'Ground: bg, an alias of paper'], ['fg', 'Text: fg, an alias of ink'], ['muted', 'Secondary text: muted'], ['ver', 'The pin: ver']]], ['Dark', 'theme=dark, ground=tile', [['bg', 'Ground: bg, an alias of ink'], ['fg', 'Text: fg, an alias of cream'], ['muted', 'Secondary text: muted'], ['ver', 'The pin: ver']]]]) {
  const pn = fr(r4, mode + ' panel', 'VERTICAL', { g: 'space/24', ...pads('space/32') }); pn.layoutSizingHorizontal = 'FILL'; pn.cornerRadius = 8; pn.setExplicitVariableModeForCollection(coll, modeId(mode)); fill(pn, 'bg'); stroke(pn, 'ink', 0.12);
  await tx(pn, mode, 'Caption', { w: 'fill', fill: 'muted', name: 'Mode' });
  const rw = fr(pn, 'Panel row', 'HORIZONTAL', { g: 'space/32' }); rw.layoutSizingHorizontal = 'FILL'; rw.counterAxisAlignItems = 'CENTER';
  rw.appendChild(tile(tnm));
  const ls = fr(rw, 'Roles', 'VERTICAL', { g: 'space/12' }); ls.layoutSizingHorizontal = 'FILL';
  for (const [v, lbl] of rows) { const rr = fr(ls, 'Role ' + v, 'HORIZONTAL', { g: 'space/12' }); rr.layoutSizingHorizontal = 'FILL'; rr.counterAxisAlignItems = 'CENTER'; const ch = shape(rr, 'rect', 'Chip', 24, 24); ch.cornerRadius = 4; fill(ch, v); stroke(ch, 'fg', 0.2); await tx(rr, lbl, 'Body/S', { w: 'fill', name: 'Role' }); }
}
return finish(P);
