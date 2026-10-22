// Page 1, Overview: what Limn does, the form grammar, the system map.
const SRC = ['Participants were asked to read each section.', 'The study covers one round of review.', 'Each section is written for its readers.', 'Comments are pinned to the page as they come.', 'Every pin points back to its line of source.'];
const FORMS = [['Dot', 'pointing', 'The pin: the spot you point at on the page.'], ['Line', 'source', 'The line of source the pin resolves to, drawn as the stem of the i.'], ['Light', 'revealing', 'A sweep across the word that reveals where the pin lands.'], ['Ripple', 'passing on', 'A ring that spreads once when a new pin arrives: the pin is passed on.']];
const MAP = [['Marks', 'The drawings that identify Limn.', [['Logo', 'Wordmark, rim mark and lockup; construction, clear space, misuse.'], ['App icon', 'The i on its grid, sized and pixel drawings, favicon, home-screen icon.']]],
  ['Foundations', 'The values every mark and screen is built from.', [['Color', 'Six tokens and the contrast table.'], ['Typeface', 'Limn Sans: weights, sets, features and sizes.'], ['Motion', 'Curves and timings for pin drop, write, ripple and light.']]],
  ['In use', 'Where the system meets a screen.', [['In use', 'The app, browser tabs and the Dock.'], ['Developers', 'CSS tokens, @font-face, favicon links, downloads.']]],
  ['Kit', 'What to take and how it may be used.', [['Library', 'Figma variables, text styles and components.'], ['License', 'The font license, the trademark, contact.']]]];
const { P, secs } = await shell([]);
const idx = {}; D.pages.forEach((p, i) => { idx[p] = String(i).padStart(2, '0'); });

// 1 What Limn does
const s1 = await sect(secs, 'What Limn does', 'Point at a spot on the PDF and Limn hands back the source line that produced it, so every fix lands in the right place.');
const r1 = fr(s1, 'Flow', 'HORIZONTAL', { g: 'space/24' }); r1.layoutSizingHorizontal = 'FILL'; r1.counterAxisAlignItems = 'CENTER';
const A = fr(r1, 'PDF page', 'VERTICAL', { g: 'space/16', ...pads('space/32') }); A.layoutSizingHorizontal = 'FILL'; A.cornerRadius = 8; stroke(A, 'ink', 0.12);
await tx(A, D.label, 'Caption', { w: 'fill', fill: 'muted', name: 'Label' });
for (let i = 0; i < 5; i++) {
  const row = fr(A, 'Text line', 'HORIZONTAL', { g: 'space/12' }); row.layoutSizingHorizontal = 'FILL'; row.counterAxisAlignItems = 'CENTER';
  const slot = N.createFrame(); slot.name = 'Pin slot'; slot.fills = []; slot.clipsContent = false; row.appendChild(slot); slot.resize(16, 16);
  if (i === 2) { const e = shape(slot, 'ellipse', 'Pin', 16, 16); e.x = 0; e.y = 0; fill(e, 'ver'); }
  const bar = shape(row, 'rect', 'Text', 100, 8); bar.cornerRadius = 4; fill(bar, 'ink', 0.12); bar.layoutSizingHorizontal = 'FILL'; bar.layoutSizingVertical = 'FIXED';
}
const chip = fr(A, 'Pin note', 'VERTICAL', { ...pads('space/12') }); chip.layoutSizingHorizontal = 'FILL'; chip.cornerRadius = 8; fill(chip, 'cream');
await tx(chip, D.note, 'Body/S', { w: 'fill', name: 'Note' });
const arrow = await tx(r1, '→', 'Heading/1', { w: 48, fill: 'muted', align: 'CENTER', name: 'Arrow' });
const B = fr(r1, 'Source', 'VERTICAL', { g: 'space/8', ...pads('space/32') }); B.layoutSizingHorizontal = 'FILL'; B.cornerRadius = 8; stroke(B, 'ink', 0.12);
await tx(B, 'Source', 'Caption', { w: 'fill', fill: 'muted', name: 'Label' });
for (let i = 0; i < SRC.length; i++) {
  const ln = D.line - 2 + i; const hit = ln === D.line;
  const row = fr(B, 'Source line', 'HORIZONTAL', { g: 'space/16', pl: 'space/12', pr: 'space/12', pt: 'space/4', pb: 'space/4' }); row.layoutSizingHorizontal = 'FILL'; row.cornerRadius = 4; if (hit) fill(row, 'cream');
  await tx(row, String(ln), 'Mono', { w: 32, fill: 'muted', name: 'No' });
  await tx(row, SRC[i], 'Mono', { w: 'fill', fill: hit ? 'fg' : 'muted', name: 'Code' });
}
r1.counterAxisAlignItems = 'MIN'; B.layoutSizingVertical = 'FILL'; A.layoutSizingVertical = 'FILL'; arrow.layoutSizingVertical = 'HUG';

// 2 Form grammar
const s2 = await sect(secs, 'Form grammar', 'Four forms carry the whole system: dot is pointing, line is source, light is revealing, ripple is passing on.');
const r2 = fr(s2, 'Forms row', 'HORIZONTAL', { g: 'space/24' }); r2.layoutSizingHorizontal = 'FILL';
const at = (s, x, y) => { s.x = x; s.y = y; return s; };
for (const [nm, mean, txt] of FORMS) {
  const c = fr(r2, 'Form/' + nm, 'VERTICAL', { g: 'space/12' }); c.layoutSizingHorizontal = 'FILL';
  const a = fr(c, 'Glyph area', 'VERTICAL', { ...pads('space/24') }); a.layoutSizingHorizontal = 'FILL'; a.primaryAxisAlignItems = 'CENTER'; a.counterAxisAlignItems = 'CENTER'; a.cornerRadius = 8; stroke(a, 'ink', 0.12);
  const g = N.createFrame(); g.name = 'Glyph ' + nm; g.fills = []; g.clipsContent = false; a.appendChild(g); g.resize(120, 120);
  if (nm === 'Dot') fill(at(shape(g, 'ellipse', 'Pin', 40, 40), 40, 40), 'ver');
  if (nm === 'Line') { const r = at(shape(g, 'rect', 'Stem', 12, 80), 54, 20); r.topLeftRadius = 6; r.topRightRadius = 6; fill(r, 'ink'); }
  if (nm === 'Light') { const b = at(shape(g, 'rect', 'Lit band', 120, 28), 0, 46); b.cornerRadius = 14; fill(b, 'cream'); for (const [y, w, op] of [[16, 96, 0.2], [56, 96, 1], [96, 72, 0.2]]) { const r = at(shape(g, 'rect', 'Line', w, 8), 12, y); r.cornerRadius = 4; fill(r, 'ink', op); } }
  if (nm === 'Ripple') { for (const [x, d, op] of [[4, 112, 0.15], [24, 72, 0.3]]) { const e = at(shape(g, 'ellipse', 'Ring', d, d), x, x); e.fills = []; stroke(e, 'ink', op, 2); } fill(at(shape(g, 'ellipse', 'Pin', 28, 28), 46, 46), 'ver'); }
  await tx(c, nm + ': ' + mean, 'Heading/3', { w: 'fill', name: 'Title' });
  await tx(c, txt, 'Body/S', { w: 'fill', fill: 'muted', name: 'Text' });
}

// 3 System map
const s3 = await sect(secs, 'System map', 'Every page of this file belongs to one of four groups.');
const r3 = fr(s3, 'Map row', 'HORIZONTAL', { g: 'space/24' }); r3.layoutSizingHorizontal = 'FILL';
for (const [gn, gd, pgs] of MAP) {
  const c = fr(r3, 'Group/' + gn, 'VERTICAL', { g: 'space/12', pt: 'space/16' }); c.layoutSizingHorizontal = 'FILL'; hair(c, 'Top', 0.25);
  await tx(c, gn, 'Heading/3', { w: 'fill', name: 'Group' });
  await tx(c, gd, 'Body/S', { w: 'fill', fill: 'muted', name: 'Group note' });
  for (const [pn, pd] of pgs) {
    const row = fr(c, 'Page/' + pn, 'HORIZONTAL', { g: 'space/12', pt: 'space/8' }); row.layoutSizingHorizontal = 'FILL'; row.counterAxisAlignItems = 'BASELINE';
    await tx(row, idx[pn], 'Mono', { w: 24, fill: 'muted', name: 'No' });
    const col = fr(row, 'Text', 'VERTICAL', { g: 'space/4' }); col.layoutSizingHorizontal = 'FILL';
    await tx(col, pn, 'Body/M', { w: 'fill', name: 'Name' });
    await tx(col, pd, 'Body/S', { w: 'fill', fill: 'muted', name: 'Text' });
  }
}
return finish(P);
