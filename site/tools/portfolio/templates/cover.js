// Page 0, Cover: wordmark, one line, contents, version, date, repository. The frame keeps its node id on a rerun.
const set = await lib('wordmarkSet', 'Logo/Wordmark');
const art = set.children.find(c => c.name === 'theme=light, ground=art only'); if (!art) throw new Error('no art-only wordmark variant');
let cover = page.children.find(c => c.type === 'FRAME' && c.name === CFG.frameName);
if (cover) for (const c of [...cover.children]) c.remove(); else { cover = N.createAutoLayout('VERTICAL'); cover.name = CFG.frameName; page.appendChild(cover); }
cover.layoutMode = 'VERTICAL'; cover.layoutSizingHorizontal = 'FIXED'; cover.layoutSizingVertical = 'FIXED'; cover.resize(1440, 900);
// the fill is emptied first: a reused frame keeps the old paint's resolved color otherwise
cover.clipsContent = false; cover.fills = []; fill(cover, 'bg'); cover.paddingLeft = 80; cover.paddingRight = 80; cover.paddingTop = 80; cover.paddingBottom = 64; cover.primaryAxisAlignItems = 'SPACE_BETWEEN';
cover.layoutGrids = [{ pattern: 'COLUMNS', alignment: 'STRETCH', gutterSize: 24, count: 12, offset: 80, visible: true, color: { r: 0.08, g: 0.086, b: 0.1, a: 0.06 } }];
await tx(cover, 'Limn Design System', 'Body/S', { w: 400, fill: 'muted', name: 'Eyebrow' });
const mid = fr(cover, 'Hero', 'HORIZONTAL', { g: 'space/24' }); mid.layoutSizingHorizontal = 'FILL'; mid.counterAxisAlignItems = 'MAX';
const left = fr(mid, 'Wordmark and line', 'VERTICAL', { g: 'space/48' }); left.layoutSizingHorizontal = 'FILL';
const wm = art.createInstance(); left.appendChild(wm); wm.rescale(3.4); wm.name = 'Logo/Wordmark';
await tx(left, D.tagline, 'Heading/1', { w: 640, name: 'Line' });
const right = fr(mid, 'Contents', 'VERTICAL', { g: 'space/8' }); right.resize(410, 100); right.layoutSizingHorizontal = 'FIXED'; right.layoutSizingVertical = 'HUG';
await tx(right, 'Contents', 'Caption', { w: 410, fill: 'muted' });
const rl = N.createRectangle(); rl.name = 'Rule'; right.appendChild(rl); rl.resize(10, 1); fill(rl, 'ink', 0.12); rl.layoutSizingHorizontal = 'FILL'; rl.layoutSizingVertical = 'FIXED';
for (let i = 1; i < D.pages.length; i++) {
  const row = fr(right, 'Row ' + D.pages[i], 'HORIZONTAL', { g: 'space/16', pt: 'space/4', pb: 'space/4' }); row.layoutSizingHorizontal = 'FILL'; row.counterAxisAlignItems = 'CENTER';
  await tx(row, String(i).padStart(2, '0'), 'Mono', { w: 32, fill: 'muted', name: 'No' });
  await tx(row, D.pages[i], 'Body/M', { w: 300, name: 'Page' });
}
const meta = fr(cover, 'Meta', 'HORIZONTAL', { g: 'space/24', pt: 'space/24' }); meta.layoutSizingHorizontal = 'FILL'; hair(meta, 'Top');
let repoText;
for (const [k, v] of [['Version', D.version], ['Date', D.date], ['Repository', D.repo]]) {
  const c = fr(meta, k, 'VERTICAL', { g: 'space/4' }); c.layoutSizingHorizontal = 'FILL';
  await tx(c, k, 'Caption', { w: 300, fill: 'muted', name: 'Label' });
  const t = await tx(c, v, 'Body/M', { w: 380, name: 'Value' });
  if (k === 'Repository') repoText = t;
}
repoText.setRangeHyperlink(0, repoText.characters.length, { type: 'URL', value: 'https://' + D.repo });
cover.x = 0; cover.y = 0;
for (const [n, k, op] of OP) n[k] = [{ ...n[k][0], opacity: op }];
return { page: CFG.pageName, frame: cover.id, size: [cover.width, cover.height], topLevel: page.children.map(c => c.name + ' ' + c.id) };
