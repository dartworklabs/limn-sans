// Built by tools/portfolio/pages_public.py from templates/prelude.js and templates/<page>.js.
// Rebuilds one page of the public file "Limn Design System" in place from D, the data of manifest.json, and from the
// figures uploaded to the page (frames named fig-<key>); see pages_public.py for the steps.
const N = figma;
const CFG = __CFG__;
const D = __DATA__;
const page = N.root.children.find(p => p.id === CFG.pageId);
if (!page || page.name !== CFG.pageName) throw new Error('page ' + CFG.pageId + ' is not named ' + CFG.pageName);
await N.setCurrentPageAsync(page);
const V = {}; for (const v of await N.variables.getLocalVariablesAsync()) V[v.name] = v;
const S = {}; for (const s of await N.getLocalTextStylesAsync()) S[s.name] = s;
await Promise.all([['Inter', 'Regular'], ['Inter', 'Medium'], ['Inter', 'Semi Bold'], ['Inter', 'Bold'], ['JetBrains Mono', 'Regular']].map(([family, style]) => N.loadFontAsync({ family, style })));
const lib = async (key, name) => { const n = await N.getNodeByIdAsync(CFG.lib[key]); if (!n || !n.name.startsWith(name)) throw new Error('library node ' + key + ' (' + CFG.lib[key] + ') is not ' + name); return n; };
const OP = [];
const paint = name => { if (!V[name]) throw new Error('no variable ' + name); return N.variables.setBoundVariableForPaint({ type: 'SOLID', color: { r: 0, g: 0, b: 0 } }, 'color', V[name]); };
const fill = (n, name, op = 1) => { n.fills = [paint(name)]; if (op !== 1) { n.fills = [{ ...n.fills[0], opacity: op }]; OP.push([n, 'fills', op]); } };
const stroke = (n, name, op = 1, w = 1) => { n.strokes = [paint(name)]; n.strokeWeight = w; n.strokeAlign = 'INSIDE'; if (op !== 1) { n.strokes = [{ ...n.strokes[0], opacity: op }]; OP.push([n, 'strokes', op]); } };
const hair = (n, side, op = 0.12) => { n.strokes = [paint('ink')]; n.strokeAlign = 'INSIDE'; for (const s of ['Top', 'Bottom', 'Left', 'Right']) n['stroke' + s + 'Weight'] = s === side ? 1 : 0; n.strokes = [{ ...n.strokes[0], opacity: op }]; OP.push([n, 'strokes', op]); };
const M = { g: 'itemSpacing', cg: 'counterAxisSpacing', pl: 'paddingLeft', pr: 'paddingRight', pt: 'paddingTop', pb: 'paddingBottom' };
const sp = (n, o) => { for (const k in o) { if (typeof o[k] === 'number') n[M[k]] = o[k]; else { if (!V[o[k]]) throw new Error('no variable ' + o[k]); n.setBoundVariable(M[k], V[o[k]]); } } };
const pads = v => ({ pl: v, pr: v, pt: v, pb: v });
const fr = (parent, name, dir, o = {}) => { const f = N.createAutoLayout(dir); f.name = name; f.fills = []; f.clipsContent = false; if (parent) parent.appendChild(f); sp(f, o); return f; };
const tx = async (parent, str, style, o = {}) => { if (!S[style]) throw new Error('no text style ' + style); const t = N.createText(); parent.appendChild(t); await t.setTextStyleIdAsync(S[style].id); t.characters = str; t.name = o.name || str.slice(0, 30); fill(t, o.fill || 'fg'); if (o.align) t.textAlignHorizontal = o.align; if (o.w && o.w !== 'fill') t.resize(o.w, 20); t.textAutoResize = 'HEIGHT'; if (o.w === 'fill') t.layoutSizingHorizontal = 'FILL'; return t; };
const shape = (parent, kind, name, w, h) => { const s = kind === 'ellipse' ? N.createEllipse() : N.createRectangle(); s.name = name; parent.appendChild(s); s.resize(w, h); return s; };
const cw = k => Math.round((k * (1280 - 264) / 12 + (k - 1) * 24) * 100) / 100;
const sect = async (parent, title, desc) => { const s = fr(parent, 'Section/' + title, 'VERTICAL', { g: 'space/24', pt: 'space/32' }); s.layoutSizingHorizontal = 'FILL'; hair(s, 'Top'); const h = fr(s, 'Heading block', 'VERTICAL', { g: 'space/8' }); h.layoutSizingHorizontal = 'FILL'; await tx(h, title, 'Heading/1', { w: 'fill', name: 'Heading' }); if (desc) await tx(h, desc, 'Body/M', { w: 720, fill: 'muted', name: 'Description' }); return s; };
const fcard = async (parent, o) => { const c = fr(parent, o.name, 'VERTICAL', { g: 'space/12' }); if (o.w === 'fill' || !o.w) c.layoutSizingHorizontal = 'FILL'; else { c.resize(o.w, 10); c.layoutSizingHorizontal = 'FIXED'; c.layoutSizingVertical = 'HUG'; } if (o.title) await tx(c, o.title, 'Heading/3', { w: 'fill', name: 'Title' }); const pad = o.pad === undefined ? 'space/32' : o.pad; const a = fr(c, 'Figure', 'VERTICAL', { pl: pad, pr: pad, pt: pad, pb: pad }); a.layoutSizingHorizontal = 'FILL'; a.primaryAxisAlignItems = 'CENTER'; a.counterAxisAlignItems = 'CENTER'; a.cornerRadius = 8; a.clipsContent = true; if (o.ground) fill(a, o.ground); if (o.stroke !== false) stroke(a, 'ink', 0.12); if (o.minH) a.minHeight = o.minH; if (o.cap) await tx(c, o.cap, o.capStyle || 'Caption', { w: 'fill', fill: o.capStyle ? 'fg' : 'muted', name: 'Caption' }); return { c, a }; };
// a table: cols = [{ w, style, muted, align }], head and rows are arrays of strings
const table = async (parent, name, cols, head, rows) => { const t = fr(parent, name, 'VERTICAL'); t.layoutSizingHorizontal = 'FILL'; const mk = async (cells, hdr) => { const r = fr(t, hdr ? 'Header' : 'Row', 'HORIZONTAL', { g: 'space/24', pt: 'space/12', pb: 'space/12' }); r.layoutSizingHorizontal = 'FILL'; r.counterAxisAlignItems = 'CENTER'; hair(r, 'Bottom', hdr ? 0.25 : 0.12); for (let i = 0; i < cells.length; i++) await tx(r, cells[i], hdr ? 'Caption' : (cols[i].style || 'Body/S'), { w: cols[i].w, fill: hdr || cols[i].muted ? 'muted' : 'fg', align: cols[i].align, name: hdr ? 'Head' : 'Cell' }); }; await mk(head, true); for (const r of rows) await mk(r, false); return t; };

// --- figures: uploaded as fig-<key> on the page; a rerun reuses the Figure/<key> frames of the previous run
const HEX = { '15161a': 'ink', 'e8452c': 'ver', 'fbfaf7': 'paper', 'fbf1e6': 'bone', 'f4ede1': 'cream', 'fff3e6': 'sky', '6d6a64': 'muted' };
const hx = c => [c.r, c.g, c.b].map(x => Math.round(x * 255).toString(16).padStart(2, '0')).join('');
// every colour that is a token is bound to its variable; annot: vermilion on dimension marks becomes ink, the pin (a near-square vector) stays vermilion
const bindTree = (root, annot) => { let n = 0, kept = 0; for (const node of [root, ...root.findAll(() => true)]) for (const key of ['fills', 'strokes']) { const a = node[key]; if (!Array.isArray(a) || !a.length) continue; if (key === 'fills' && node.strokes && node.strokes.length && a.every(p => p.type === 'SOLID' && hx(p.color) === '000000')) { node.fills = []; continue; } const ops = a.map(p => p.opacity); let ch = false; const b = a.map(p => { if (p.type !== 'SOLID') return p; let nm = HEX[hx(p.color)]; if (!nm) { kept++; return p; } const pinLike = Math.abs(node.width - node.height) < 1 && node.width > 14 && node.width < 70; if (nm === 'ver' && annot && !pinLike) nm = 'ink'; ch = true; n++; return paint(nm); }); if (ch) { node[key] = b; node[key] = node[key].map((q, i) => q.type === 'SOLID' && ops[i] !== undefined && ops[i] !== 1 ? { ...q, opacity: ops[i] } : q); } } return { bound: n, kept }; };
const rootFig = key => page.children.find(n => n.type === 'FRAME' && n.name === 'fig-' + key);
// place figure <key> in parent at its natural size times o.scale (the manifest width is the natural size)
const fig = (parent, key, o = {}) => { const f = rootFig(key); if (!f) throw new Error('figure ' + key + ' is missing'); f.fills = []; f.clipsContent = false; f.name = 'Figure/' + key; const nat = D.figs[key]; const k0 = nat / f.width; if (Math.abs(k0 - 1) > 1e-3) f.rescale(k0); bindTree(f, o.annot); parent.appendChild(f); if (o.scale && o.scale !== 1) f.rescale(o.scale); return f; };
const figName = n => n.name.startsWith('Figure/') && n.type === 'FRAME';
// the page frame: keeps its node id on a rerun; its Sections are cleared and rebuilt. need = figure keys the page uses
const shell = async (need) => {
  let P = page.children.find(c => c.type === 'FRAME' && c.name === CFG.frameName);
  let secs = P && P.findOne(n => n.name === 'Sections');
  if (P && !secs) { P.remove(); P = null; }   // an empty placeholder frame of the same name
  const have = new Set(page.children.filter(n => n.name.startsWith('fig-')).map(n => n.name.slice(4)));
  if (P) for (const f of P.findAll(figName)) have.add(f.name.slice(7));
  const miss = need.filter(k => !have.has(k));
  if (miss.length) throw new Error('missing figures, upload them first: ' + miss.join(', '));
  if (P) for (const f of P.findAll(figName)) { const k = f.name.slice(7); if (rootFig(k)) f.remove(); else { f.name = 'fig-' + k; page.appendChild(f); } }
  if (!P) { const inst = (await lib('pageFrame', 'Page/Frame')).createInstance(); page.appendChild(inst); P = inst.detachInstance(); P.name = CFG.frameName; secs = P.findOne(n => n.name === 'Sections'); }
  else for (const c of [...secs.children]) c.remove();
  const ti = P.findOne(n => n.type === 'INSTANCE' && n.name === 'Page/Title'), fi = P.findOne(n => n.type === 'INSTANCE' && n.name === 'Page/Footer');
  const kk = (o, p) => Object.keys(o.componentProperties).find(k => k.startsWith(p));
  ti.setProperties({ [kk(ti, 'number')]: CFG.number, [kk(ti, 'title')]: CFG.title, [kk(ti, 'lede')]: CFG.lede });
  fi.setProperties({ [kk(fi, 'page')]: CFG.title });
  fi.strokes = [{ ...fi.strokes[0], opacity: 0.12 }]; OP.push([fi, 'strokes', 0.12]);
  secs.strokes = []; secs.dashPattern = []; secs.minHeight = null;
  return { P, secs };
};
// last step: put the frame at the origin, re-apply the paint opacities, delete uploads nobody used
const finish = (P, extra = {}) => {
  P.x = 0; P.y = 0;
  for (const [n, k, op] of OP) n[k] = [{ ...n[k][0], opacity: op }];
  const stale = page.children.filter(n => n.name.startsWith('fig-')); for (const n of stale) n.remove();
  return { page: CFG.pageName, frame: P.id, size: [P.width, Math.round(P.height)], topLevel: page.children.map(c => c.name + ' ' + c.id), staleUploadsRemoved: stale.length, ...extra };
};
