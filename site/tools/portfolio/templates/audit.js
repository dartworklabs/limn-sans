// QA of one rebuilt page: private strings, history words, Hangul, overflow, unbound colors, text sizing, numbers, tables.
// Built by pages_public.py audit; read-only. ok is true when every list is empty.
const N = figma;
const CFG = __CFG__;
const page = N.root.children.find(p => p.id === CFG.pageId);
if (!page || page.name !== CFG.pageName) throw new Error('page ' + CFG.pageId + ' is not named ' + CFG.pageName);
await N.setCurrentPageAsync(page);
const FORB = CFG.forbidden.map(s => s.toLowerCase()), HIST = new RegExp(CFG.hist, 'i'), HAN = /[ᄀ-ᇿ㄰-㆏가-힣]/, A = new Set(CFG.allowed);
const all = page.findAll(() => true);
const out = { page: CFG.pageName, nodes: all.length, topLevel: page.children.map(c => c.name), forb: [], hist: [], han: [], overflow: [], rawUI: [], textBad: [], figClip: [], numbers: [], tables: [], leftovers: [] };
const inFig = n => { let p = n; while (p && p.type !== 'PAGE') { if (p.name.startsWith('Figure/')) return true; p = p.parent; } return false; };
const inInst = n => { let p = n.parent; while (p && p.type !== 'PAGE') { if (p.type === 'INSTANCE') return true; p = p.parent; } return false; };
for (const c of page.children) if (c.name.startsWith('fig-') || c.name.startsWith('zz')) out.leftovers.push(c.id + ' ' + c.name);
for (const n of [page, ...all]) {
  const strs = [n.name]; if ('description' in n && n.description) strs.push(n.description); if (n.type === 'TEXT') strs.push(n.characters);
  for (const s of strs) { const l = s.toLowerCase(); for (const f of FORB) if (l.includes(f)) out.forb.push(n.id + ' ' + f); if (HIST.test(s)) out.hist.push(n.id + ' ' + s.slice(0, 50)); if (HAN.test(s)) out.han.push(n.id + ' ' + s.slice(0, 40)); }
  if (n.type === 'TEXT') {
    if (n.textAutoResize !== 'HEIGHT' || !n.textStyleId) out.textBad.push(n.id + ' ' + n.characters.slice(0, 20));
    const s = n.characters.replace(/#[0-9a-fA-F]{6}\b/g, ' ');
    for (const m of s.match(/\d+(?:\.\d+)?/g) || []) if (!A.has(m) && !/^0\d$/.test(m) && m !== '10' && m !== String(CFG.year)) out.numbers.push(m + ' in "' + n.characters.slice(0, 40) + '"');
  }
  if (n.type === 'FRAME' && n.name.startsWith('Figure/') && n.clipsContent) out.figClip.push(n.id);
  if ('clipsContent' in n && n.clipsContent && 'children' in n && n.children.length && n.type !== 'PAGE') { const b = n.absoluteBoundingBox; if (b) for (const c of n.children) { const cb = c.absoluteBoundingBox; if (cb && (cb.x < b.x - 0.6 || cb.y < b.y - 0.6 || cb.x + cb.width > b.x + b.width + 0.6 || cb.y + cb.height > b.y + b.height + 0.6)) out.overflow.push(n.id + ' ' + n.name + ' > ' + c.id + ' ' + c.name); } }
  if (!inInst(n) && !inFig(n)) for (const key of ['fills', 'strokes']) { const a = n[key]; if (!Array.isArray(a)) continue; for (const p of a) if (p.visible !== false && (p.type !== 'SOLID' || !(p.boundVariables && p.boundVariables.color))) out.rawUI.push(n.id + ' ' + n.name + ' ' + key + ' ' + p.type); }
}
// the tables as rendered must equal the rows built from the manifest
for (const [name, e] of Object.entries(CFG.expectTables)) {
  const t = page.findOne(n => n.type === 'FRAME' && n.name === name);
  if (!t) { out.tables.push('missing table ' + name); continue; }
  const got = t.children.map(r => r.children.slice(e.skip || 0).map(c => (c.type === 'TEXT' ? c.characters : c.findAll(x => x.type === 'TEXT').map(x => x.characters).join(' '))));
  if (JSON.stringify(got) !== JSON.stringify(e.rows)) out.tables.push(name + ': got ' + JSON.stringify(got) + ' expected ' + JSON.stringify(e.rows));
}
for (const s of CFG.expectTexts) if (!all.some(n => n.type === 'TEXT' && n.characters === s)) out.tables.push('missing text ' + s);
out.ok = ['forb', 'hist', 'han', 'overflow', 'rawUI', 'textBad', 'figClip', 'numbers', 'tables', 'leftovers'].every(k => out[k].length === 0);
return out;
