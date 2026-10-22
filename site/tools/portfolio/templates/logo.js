// Page 2, Logo: marks, construction, clear space, minimum size, color variants, misuse.
const wset = await lib('wordmarkSet', 'Logo/Wordmark');
const tile = nm => { const c = wset.children.find(x => x.name === nm); if (!c) throw new Error('no wordmark variant ' + nm); return c.createInstance(); };
const minH = Math.min(...D.mingd.map(x => +x[0])), gdFrom = +D.mingd.find(x => x[1] === D.gd)[0];
const { P, secs } = await shell(D.need);

// 1 Marks
const s1 = await sect(secs, 'Marks', 'Use the wordmark alone, or with the rim mark as the lockup. Take the library components; never redraw a mark.');
const r1 = fr(s1, 'Marks row', 'HORIZONTAL', { g: 'space/24' }); r1.layoutSizingHorizontal = 'FILL';
const marks = [[tile('theme=light, ground=tile'), D.marks[0], 'Wordmark'], [(await lib('lockup', 'Logo/Lockup')).createInstance(), D.marks[1], 'Lockup'], [(await lib('rim', 'Logo/Rim')).createInstance(), D.marks[2], 'Rim mark']];
for (const [inst, cap, nm] of marks) { const { a } = await fcard(r1, { name: nm, cap, pad: 0, minH: 200, ground: 'paper' }); a.appendChild(inst); }

// 2 Construction
const s2 = await sect(secs, 'Construction', 'Every measure follows from the stroke s. Values are in font units, em ' + D.upm + '.');
const { a: a2 } = await fcard(s2, { name: 'Construction figure', cap: D.cons });
fig(a2, 'logo-construction', { annot: true });
await table(s2, 'Measures', [{ w: 240 }, { w: 120, style: 'Mono' }, { w: 'fill', muted: true }], D.tables.spec.head, D.tables.spec.rows);

// 3 Clear space
const s3 = await sect(secs, 'Clear space', "Keep the wordmark's box clear on every side by half the x-height.");
const r3 = fr(s3, 'Clear space row', 'HORIZONTAL', { g: 'space/24' }); r3.layoutSizingHorizontal = 'FILL'; r3.counterAxisAlignItems = 'MIN';
const { a: a3 } = await fcard(r3, { name: 'Clear space figure', cap: D.clear, w: cw(6) });
fig(a3, 'logo-clearspace', { annot: true, scale: 2 });
const t3 = fr(r3, 'Clear space text', 'VERTICAL', { g: 'space/12' }); t3.layoutSizingHorizontal = 'FILL';
await tx(t3, 'Half the x-height', 'Heading/3', { w: 'fill' });
await tx(t3, 'The clear space is ' + D.nums.clear + ' font units at the wordmark’s own scale, half the x-height of ' + D.nums.xh + '. The library tiles carry their own padding, which is never less than this.', 'Body/M', { w: 'fill', fill: 'muted' });

// 4 Minimum size: the labels of the pin-gap table are the keys of logo.min_gd
const s4 = await sect(secs, 'Minimum size', 'The wordmark holds down to ' + minH + ' px tall. Below ' + gdFrom + ' px the pin gap opens up, so white always shows under the pin.');
const r4 = fr(s4, 'Sizes row', 'HORIZONTAL', { g: 'space/24' }); r4.layoutSizingHorizontal = 'FILL';
for (const m of D.min) {
  const { a } = await fcard(r4, { name: 'Size ' + m.h, title: m.h + ' px tall', cap: m.cap, minH: 150, pad: 'space/24' });
  const inner = fr(a, 'Actual and enlarged', 'HORIZONTAL', { g: 'space/32' }); inner.counterAxisAlignItems = 'MAX';
  const c1 = fr(inner, 'Actual', 'VERTICAL', { g: 'space/8' }); c1.counterAxisAlignItems = 'CENTER';
  const f1 = fig(c1, m.key, {});
  await tx(c1, 'Actual size', 'Caption', { w: 72, fill: 'muted', align: 'CENTER' });
  const c2 = fr(inner, 'Enlarged', 'VERTICAL', { g: 'space/8' }); c2.counterAxisAlignItems = 'CENTER';
  const g = f1.clone(); c2.appendChild(g); g.rescale(3); g.name = 'Enlarged/' + m.key;
  await tx(c2, 'Enlarged', 'Caption', { w: 72, fill: 'muted', align: 'CENTER' });
}
await table(s4, 'Pin gap by height', [{ w: 160 }, ...D.tables.pingap.head.slice(1).map(() => ({ w: 'fill', style: 'Mono' }))], D.tables.pingap.head, D.tables.pingap.rows);

// 5 Color variants
const s5 = await sect(secs, 'Color variants', 'On paper and ink the pin is vermilion. On vermilion the pin joins the strokes in a light tone.');
const r5 = fr(s5, 'Variants row', 'HORIZONTAL', { g: 'space/24' }); r5.layoutSizingHorizontal = 'FILL';
for (const [nm, cap, gr] of D.vars) { const { a } = await fcard(r5, { name: nm.split(',')[0].replace('theme=', 'Wordmark on '), cap, pad: 0, minH: 200, ground: gr, stroke: gr === 'paper' }); a.appendChild(tile(nm)); }

// 6 Misuse
const s6 = await sect(secs, 'Misuse', 'The wordmark is a fixed drawing. These changes break it.');
const per = Math.ceil(D.misuse.length / 2);
for (let row = 0; row < 2; row++) {
  const rr = fr(s6, 'Misuse row ' + (row + 1), 'HORIZONTAL', { g: 'space/24' }); rr.layoutSizingHorizontal = 'FILL';
  for (const [k, cap, key] of D.misuse.slice(row * per, row * per + per)) { const { a } = await fcard(rr, { name: 'Misuse ' + k, cap, capStyle: 'Body/S', minH: 128, pad: 'space/16' }); fig(a, key, {}); }
}
return finish(P);
