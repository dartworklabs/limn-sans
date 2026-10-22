// Page 3, App icon: grid, size ramp, pixel drawings, favicon, home screen.
const iset = await lib('iconSet', 'Icon/App');
const icon = (size, theme) => { const c = iset.children.find(x => x.name === `size=${size}, theme=${theme}`); if (!c) throw new Error('no icon variant ' + size + ' ' + theme); return c.createInstance(); };
const canvas = D.grid[0][1], body = D.grid[1][1], smallest = D.px[0][0];
const { P, secs } = await shell(D.need);

// 1 Grid
const s1 = await sect(secs, 'Grid', 'The icon sits on the Apple icon grid: a ' + canvas + ' canvas, an ' + body + ' squircle and the i centered on it.');
const r1 = fr(s1, 'Grid row', 'HORIZONTAL', { g: 'space/24' }); r1.layoutSizingHorizontal = 'FILL';
const { a: a1 } = await fcard(r1, { name: 'Grid figure', cap: D.gridCap, w: cw(8) });
fig(a1, 'icon-grid', { annot: true });
const t1 = fr(r1, 'Grid measures', 'VERTICAL', { g: 'space/12' }); t1.layoutSizingHorizontal = 'FILL';
await tx(t1, 'Measures on the ' + canvas + ' canvas', 'Heading/3', { w: 'fill' });
await table(t1, 'Grid measures table', [{ w: 'fill' }, { w: 96, style: 'Mono' }], D.tables.grid.head, D.tables.grid.rows);

// 2 Size ramp
const s2 = await sect(secs, 'Size ramp', 'The stem thickens and the pin gap opens as the icon shrinks, so the i still reads at ' + smallest + ' px. The bone squircle is the app icon; the ink row is the same drawing for dark surfaces.');
const { a: a2 } = await fcard(s2, { name: 'Ramp figure', cap: D.rampCap });
fig(a2, 'icon-ramp', {});
await table(s2, 'Stem and gap by size', [{ w: 240 }, { w: 160, style: 'Mono' }, { w: 'fill', style: 'Mono' }], D.tables.tiers.head, D.tables.tiers.rows);

// 3 Pixel drawings
const s3 = await sect(secs, 'Pixel drawings', 'At ' + D.px.map(p => p[0]).slice(0, -1).join(', ') + ' and ' + D.px[D.px.length - 1][0] + ' px the icon is drawn pixel by pixel, so every edge lands on the device pixel.');
const r3 = fr(s3, 'Pixel row', 'HORIZONTAL', { g: 'space/24' }); r3.layoutSizingHorizontal = 'FILL';
const pixAreas = [];
for (const [px, bd, st, pn, gp, rt, key, cap] of D.px) {
  const { a } = await fcard(r3, { name: 'Pixel ' + px, title: px + ' px', cap, pad: 'space/24' });
  a.itemSpacing = 24; pixAreas.push(a);
  fig(a, key, {});
  const act = fr(a, 'Actual size', 'VERTICAL', { g: 'space/8' }); act.counterAxisAlignItems = 'CENTER';
  act.appendChild(icon(px, 'light'));
  await tx(act, 'Actual size', 'Caption', { w: 96, fill: 'muted', align: 'CENTER' });
  const specs = fr(a, 'Specs', 'VERTICAL', { g: 'space/4' }); specs.layoutSizingHorizontal = 'FILL';
  await tx(specs, 'Body ' + bd + ' px, gap ' + gp + ' px' + (rt ? ', round top' : ''), 'Body/S', { w: 'fill', fill: 'muted', align: 'CENTER' });
  await tx(specs, 'Stem ' + st[0] + ' × ' + st[1] + ' px, pin ' + pn[0] + ' × ' + pn[1] + ' px', 'Body/S', { w: 'fill', fill: 'muted', align: 'CENTER' });
}
const mx = Math.max(...pixAreas.map(a => a.height)); for (const a of pixAreas) a.minHeight = mx;

// 4 Favicon
const s4 = await sect(secs, 'Favicon', 'One ink rounded square with the i fills the whole tab icon, and serves light and dark tabs alike.');
const r4 = fr(s4, 'Favicon row', 'HORIZONTAL', { g: 'space/24' }); r4.layoutSizingHorizontal = 'FILL';
const f16 = D.fav[0][0], f32 = D.fav[D.fav.length - 1][0];
for (const [nm, cap] of [['light', 'On a light tab, at ' + f16 + ' px and ' + f32 + ' px: the ink square is unchanged.'], ['dark', 'On a dark tab, at ' + f16 + ' px and ' + f32 + ' px: the same drawing.']]) { const { a } = await fcard(r4, { name: 'Favicon ' + nm, cap, pad: 'space/24' }); fig(a, 'icon-favicon-' + nm, {}); }
await table(s4, 'Favicon drawings', [{ w: 160 }, { w: 'fill', style: 'Mono' }, { w: 'fill', style: 'Mono' }, { w: 'fill', style: 'Mono' }, { w: 'fill', style: 'Mono' }], D.tables.fav.head, D.tables.fav.rows);

// 5 Home screen
const s5 = await sect(secs, 'Home screen', 'The ' + D.touch + ' px home-screen icon runs to the edge of the square; the system rounds the corners.');
const r5 = fr(s5, 'Home row', 'HORIZONTAL', { g: 'space/24' }); r5.layoutSizingHorizontal = 'FILL';
const { a: a5 } = await fcard(r5, { name: 'Home screen icon', cap: D.touchCap, w: cw(4), pad: 'space/32' });
a5.appendChild(icon(String(D.touch), 'light'));
const t5 = fr(r5, 'Home text', 'VERTICAL', { g: 'space/12' }); t5.layoutSizingHorizontal = 'FILL';
await tx(t5, 'Full bleed', 'Heading/3', { w: 'fill' });
await tx(t5, 'The drawing carries no rounded corners of its own. The system applies its corner mask to the full square, so the body runs edge to edge.', 'Body/M', { w: 'fill', fill: 'muted' });
return finish(P);
