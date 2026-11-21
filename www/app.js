// Interface: list, 3D view, information, animations, textures, export. All data comes from the local
// server (api/*), which reads the user's own disc image.
import { View3D } from './view3d.js';

const $ = s => document.querySelector(s);
const T = {
  de: {
    open: 'Abbild öffnen …', nodisc: 'Kein Abbild geöffnet', lang: 'Sprache', search: 'Name, Kürzel oder Nummer …',
    f_all: 'Alle Modelle', f_partner: 'Partner', f_enemy: 'Gegner', f_other: 'Ohne Kämpfer',
    hint: 'Öffne dein eigenes Abbild von Digimon World 3 (USA) oder Digimon World 2003 (PAL). Es werden keine Spieldaten mitgeliefert.',
    loading: 'Modell wird gelesen …', m_orig: 'Original', m_hd: 'HD', nearest: 'PS1-Pixel (nearest)', wire: 'Drahtgitter',
    grid: 'Gitter', cull: 'Rückseiten ausblenden', skel: 'Skelett', bg: 'Hintergrund', center: 'Zentrieren', shot: 'Bild speichern',
    speed: 'Tempo', loop: 'Schleife', t_info: 'Info', t_anim: 'Animationen', t_tex: 'Texturen', t_exp: 'Export',
    noselect: 'Kein Modell gewählt.', compare: 'Vergleichen mit',
    hdnote: 'HD: eigene PNG je Texturseite, beliebige Größe (z. B. 2048 × 4096), ohne Farbreduzierung. Wird für dieses Modell gespeichert und beim nächsten Öffnen wieder geladen.',
    e_glb: 'glTF/GLB (Skelett + alle Animationen)', e_obj: 'OBJ + MTL + PNG (Ruhepose)', e_png: 'Texturen als PNG',
    e_mot: 'Animationen als JSON (30 Bilder/s)', e_json: 'Technische Daten als JSON', e_hd: 'HD-Texturen dieses Modells',
    models: n => `${n} Modelle`, of: (a, b) => `${a} von ${b}`, frames: 'Bilder', seconds: 's', nogl: 'Keine glTF-Daten für diese Motion',
    k_model: 'Modell', k_file: 'Datei', k_id: 'Modell-ID', k_name: 'Name', k_namesrc: 'Name laut', k_variant: 'Art', k_bones: 'Knochen',
    k_verts: 'Vertices (Spiel)', k_faces: 'Polygone (Spiel)', k_tq: 'davon Dreiecke / Vierecke', k_gpu: 'Dreiecke / Vertices (Anzeige)',
    k_tex: 'Texturseiten', k_mot: 'Motions', k_data: 'Datenbereiche', k_lba: 'Sektor (LBA)', k_size: 'Größe', k_fnum: 'Dateinummer',
    k_fighters: 'Kämpfer', k_scripts: 'Aktionsskripte', k_face: 'Gesichtsbereiche', none: '—', import: 'HD-PNG …', remove: 'Entfernen',
    hdon: 'HD', hdoff: 'kein HD', exported: n => `${n} Datei(en) geschrieben`, saved: 'Gespeichert', end: 'Ende',
    end_loop: 'Schleife', end_hold: 'hält', end_idle: 'zurück zu Idle', partner: 'Partner', enemy: 'Gegner',
  },
  en: {
    open: 'Open image …', nodisc: 'No image open', lang: 'Language', search: 'Name, code or number …',
    f_all: 'All models', f_partner: 'Partners', f_enemy: 'Enemies', f_other: 'No fighter',
    hint: 'Open your own disc image of Digimon World 3 (USA) or Digimon World 2003 (PAL). No game data is included.',
    loading: 'Reading model …', m_orig: 'Original', m_hd: 'HD', nearest: 'PS1 pixels (nearest)', wire: 'Wireframe',
    grid: 'Grid', cull: 'Hide back faces', skel: 'Skeleton', bg: 'Background', center: 'Center', shot: 'Save image',
    speed: 'Speed', loop: 'Loop', t_info: 'Info', t_anim: 'Animations', t_tex: 'Textures', t_exp: 'Export',
    noselect: 'No model selected.', compare: 'Compare with',
    hdnote: 'HD: your own PNG per texture page, any size (e.g. 2048 × 4096), no colour reduction. Saved for this model and loaded again next time.',
    e_glb: 'glTF/GLB (skeleton + all animations)', e_obj: 'OBJ + MTL + PNG (rest pose)', e_png: 'Textures as PNG',
    e_mot: 'Animations as JSON (30 frames/s)', e_json: 'Technical data as JSON', e_hd: 'HD textures of this model',
    models: n => `${n} models`, of: (a, b) => `${a} of ${b}`, frames: 'frames', seconds: 's', nogl: 'No glTF data for this motion',
    k_model: 'Model', k_file: 'File', k_id: 'Model ID', k_name: 'Name', k_namesrc: 'Name from', k_variant: 'Kind', k_bones: 'Bones',
    k_verts: 'Vertices (game)', k_faces: 'Polygons (game)', k_tq: 'triangles / quads', k_gpu: 'Triangles / vertices (shown)',
    k_tex: 'Texture pages', k_mot: 'Motions', k_data: 'Data areas', k_lba: 'Sector (LBA)', k_size: 'Size', k_fnum: 'File number',
    k_fighters: 'Fighters', k_scripts: 'Action scripts', k_face: 'Face areas', none: '—', import: 'HD PNG …', remove: 'Remove',
    hdon: 'HD', hdoff: 'no HD', exported: n => `${n} file(s) written`, saved: 'Saved', end: 'End',
    end_loop: 'loop', end_hold: 'holds', end_idle: 'back to idle', partner: 'Partner', enemy: 'Enemy',
  },
};
let lang = (() => { try { return localStorage.getItem('lang'); } catch { return null; } })()
  || ((navigator.language || 'en').toLowerCase().startsWith('de') ? 'de' : 'en');
const t = (k, ...a) => { const v = T[lang][k] ?? T.de[k] ?? k; return typeof v === 'function' ? v(...a) : v; };

async function api(name, ...args) {
  const r = await fetch(`api/${name}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args) });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error);
  return j.data;
}
function toast(text, err = false) {
  const el = $('#toast'); el.textContent = text; el.classList.toggle('err', err); el.classList.remove('hidden');
  clearTimeout(toast.h); toast.h = setTimeout(() => el.classList.add('hidden'), err ? 9000 : 4000);
}
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const S = { info: null, catalog: [], shown: [], sel: -1, meta: null, base: '', motion: null, hd: {}, cmp: null, loadSeq: 0 };
const view = new View3D($('#c'));
window.__viewer = { view, state: S, api };

function applyLang() {
  document.documentElement.lang = lang;
  $('#lang').value = lang;
  document.querySelectorAll('[data-t]').forEach(e => { e.textContent = t(e.dataset.t); });
  document.querySelectorAll('[data-tp]').forEach(e => { e.placeholder = t(e.dataset.tp); });
  if (S.info) showGame();
  renderList();
  if (S.meta) { renderInfo(); renderAnims(); renderTex(); }
}

// ------------------------------------------------------------------ list
const norm = s => String(s ?? '').normalize('NFKC').toLowerCase().replace(/[^a-z0-9]/g, '');
function matches(m, q) {
  if (!q) return true;
  const n = q.replace(/^#/, '');
  if (/^\d+$/.test(n)) return [m.id, ...(m.fighter_ids || [])].includes(Number(n));
  const nq = norm(q);
  return [m.name, m.code, m.file, ...(m.aliases || [])].some(h => norm(h).includes(nq));
}
function renderList() {
  const q = $('#q').value.trim(), f = $('#filter').value;
  S.shown = S.catalog.filter(m => matches(m, q) && (f === 'all' || (f === 'partner' && m.fighter_ids.length && !m.enemy)
    || (f === 'enemy' && m.enemy) || (f === 'other' && !m.fighter_ids.length)));
  $('#count').textContent = S.catalog.length ? (S.shown.length === S.catalog.length ? t('models', S.catalog.length) : t('of', S.shown.length, S.catalog.length)) : '';
  $('#list').innerHTML = S.shown.map(m => `<div class="item${m.id === S.sel ? ' sel' : ''}" data-id="${m.id}">
    <span class="n">${esc(m.name)}</span><span class="tag">${m.enemy ? t('enemy') : m.fighter_ids.length ? t('partner') : '·'}</span>
    <span class="c">${esc(m.code)}</span></div>`).join('');
}
$('#list').addEventListener('click', e => { const it = e.target.closest('.item'); if (it) select(Number(it.dataset.id)); });
$('#list').addEventListener('keydown', e => {
  if (!['ArrowDown', 'ArrowUp'].includes(e.key) || !S.shown.length) return;
  e.preventDefault();
  const i = S.shown.findIndex(m => m.id === S.sel);
  const n = Math.max(0, Math.min(S.shown.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)));
  select(S.shown[n].id);
});
$('#q').addEventListener('input', renderList);
$('#filter').addEventListener('change', renderList);

// ------------------------------------------------------------------ disc
function showGame() {
  const s = S.info;
  $('#game').textContent = `${s.game} · ${s.region} · ${s.executable} · ${s.file}`;
  $('#game').title = s.names_note || '';
}
async function openDisc(path) {
  try {
    const r = await api('open', path ?? null);
    if (!r) return;
    S.info = r.summary; S.catalog = r.catalog; S.sel = -1;
    showGame(); renderList();
    if (r.summary.names_note) toast(r.summary.names_note);
    $('#list').focus();
  } catch (e) { toast(e.message, true); }
}
$('#b-open').onclick = () => openDisc();

// ------------------------------------------------------------------ model
async function select(id) {
  if (id === S.sel && S.meta) return;
  S.sel = id;
  document.querySelectorAll('#list .item').forEach(e => e.classList.toggle('sel', Number(e.dataset.id) === id));
  document.querySelector(`#list .item[data-id="${id}"]`)?.scrollIntoView({ block: 'nearest' });
  const seq = ++S.loadSeq;
  $('#busy').classList.remove('hidden');
  try {
    const r = await api('model', id);
    if (seq !== S.loadSeq) return;
    S.meta = r.meta; S.base = r.base; S.hd = r.hd;
    await view.load(S.base + 'model.glb');
    if (seq !== S.loadSeq) return;
    $('#msg').classList.add('hidden');
    await applyHd();
    $('#cmp').checked = false; S.cmp = null;
    const first = S.meta.motions.find(m => m.gltf);
    renderInfo(); renderTex();
    playMotion(first ? first.id : null);
  } catch (e) { if (seq === S.loadSeq) toast(e.message, true); }
  finally { if (seq === S.loadSeq) $('#busy').classList.add('hidden'); }
}

function texSummary(list) {
  const g = {};
  for (const x of list) { const k = `${x.width}×${x.height}, ${x.depth || ''}`; g[k] = (g[k] || 0) + 1; }
  return Object.entries(g).map(([k, n]) => `${n} × ${esc(k)}`).join('<br>');
}
function kv(rows) { return `<table class="kv">${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join('')}</table>`; }
function renderInfo() {
  const m = S.meta; if (!m) return;
  const c = m.counts, d = m.data;
  const fighters = d.fighters.map(f => `#${f.id} (${f.enemy ? t('enemy') : t('partner')}, kind ${f.kind})`).join('<br>') || t('none');
  $('#info').className = '';
  $('#info').innerHTML = `<h3>${esc(m.name)}</h3>` + kv([
    [t('k_id'), `${m.id}`], [t('k_file'), esc(m.file)], [t('k_variant'), esc(m.variant || t('none'))], [t('k_namesrc'), esc(m.name_status)],
    [t('k_bones'), c.bones], [t('k_verts'), c.vertices_native], [t('k_faces'), c.faces_native], [t('k_tq'), `${c.triangles_native} / ${c.quads_native}`],
    [t('k_gpu'), `${c.triangles_gpu} / ${c.vertices_gpu}`],
    [t('k_tex'), texSummary(m.textures)],
    [t('k_mot'), `${m.motion_count} (${m.motions.filter(x => x.gltf).length} glTF)`],
  ]) + `<h3>${t('k_data')}</h3>` + kv([
    [t('k_file'), esc(d.path)], [t('k_lba'), d.lba], [t('k_size'), `${d.size.toLocaleString()} B`], [t('k_fnum'), d.file_number ?? t('none')],
    [t('k_fighters'), fighters], [t('k_scripts'), m.scripts.length ? m.scripts.filter(s => s.motions.length).map(s => `${s.index}: ${s.motions.join(', ')}`).join('<br>') : esc(m.script_note || t('none'))],
    [t('k_face'), d.face_rects.length || t('none')],
  ]);
}

function endText(e) { return e === 'loop' ? t('end_loop') : e === 'idle' ? t('end_idle') : t('end_hold'); }
function renderAnims() {
  const m = S.meta; if (!m) return;
  $('#anims').innerHTML = m.motions.map(x => `<div class="anim${x.id === S.motion ? ' sel' : ''}${x.gltf ? '' : ' nodata'}" data-id="${x.id}" title="${esc(x.name_source || '')}">
    <div class="t"><b>${esc(lang === 'en' ? x.name_en : x.name)}</b><span class="mono dim">#${x.id}</span></div>
    <div class="s">${x.frames} ${t('frames')} · ${x.seconds.toFixed(2)} ${t('seconds')} · ${t('end')}: ${endText(x.end)}${x.gltf ? '' : ' · ' + t('nogl')}</div></div>`).join('');
  $('#cmp-motion').innerHTML = m.motions.filter(x => x.gltf).map(x => `<option value="${x.id}">#${x.id} ${esc(lang === 'en' ? x.name_en : x.name)}</option>`).join('');
}
$('#anims').addEventListener('click', e => { const a = e.target.closest('.anim'); if (a) playMotion(Number(a.dataset.id)); });

function motionById(id) { return S.meta?.motions.find(m => m.id === id); }
function playMotion(id) {
  S.motion = id;
  renderAnims();
  const m = motionById(id);
  const other = S.cmp != null ? motionById(S.cmp) : null;
  view.play(m?.gltf ?? null, other?.gltf ?? null, m?.hidden, other?.hidden);
  updateTimeline(true);
  $('#t-play').textContent = '⏸';
}

// comparison copy next to the model
$('#cmp').onchange = async () => {
  $('#cmp-motion').disabled = !$('#cmp').checked;
  S.cmp = $('#cmp').checked ? Number($('#cmp-motion').value) : null;
  await view.compare(S.base + 'model.glb', $('#cmp').checked);
  await applyHd();
  playMotion(S.motion);
};
$('#cmp-motion').onchange = () => { S.cmp = Number($('#cmp-motion').value); playMotion(S.motion); };

// ------------------------------------------------------------------ timeline
function updateTimeline(full) {
  const n = view.frames(), f = view.frameIndex();
  const pos = $('#t-pos');
  if (full) pos.max = String(Math.max(0, n - 1));
  if (!pos.matches(':active')) pos.value = String(f);
  $('#t-frame').textContent = `${Math.min(f, n - 1) + 1} / ${n}`;
  $('#t-dur').textContent = `${view.time().toFixed(2)} / ${view.duration().toFixed(2)} s`;
}
view.onTick = () => { if (S.meta) updateTimeline(false); };
$('#t-play').onclick = () => {
  if (!S.meta) return;
  if (view.playing) { view.pause(true); $('#t-play').textContent = '▶'; }
  else {
    if (!view.loop && view.frameIndex() >= view.frames() - 1) view.seekFrame(0);
    view.pause(false); $('#t-play').textContent = '⏸';
  }
};
$('#t-prev').onclick = () => { view.step(-1); $('#t-play').textContent = '▶'; };
$('#t-next').onclick = () => { view.step(1); $('#t-play').textContent = '▶'; };
$('#t-pos').oninput = () => { view.pause(true); view.seekFrame(Number($('#t-pos').value)); $('#t-play').textContent = '▶'; };
$('#t-speed').onchange = () => { view.speed = Number($('#t-speed').value); };
$('#t-loop').onchange = () => view.setLoop($('#t-loop').checked);
document.addEventListener('keydown', e => {
  if (e.target.matches('input[type=search], input[type=text], select')) return;
  if (e.key === ' ') { e.preventDefault(); $('#t-play').click(); }
  if (e.key === 'ArrowLeft') { e.preventDefault(); $('#t-prev').click(); }
  if (e.key === 'ArrowRight') { e.preventDefault(); $('#t-next').click(); }
});

// ------------------------------------------------------------------ display options
document.querySelectorAll('#mode button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#mode button').forEach(x => x.classList.toggle('on', x === b));
  view.setOption('hd', b.dataset.v === 'hd');
});
$('#o-nearest').onchange = () => view.setOption('filter', $('#o-nearest').checked ? 'nearest' : 'linear');
$('#o-wire').onchange = () => view.setOption('wireframe', $('#o-wire').checked);
$('#o-cull').onchange = () => view.setOption('cull', $('#o-cull').checked);
$('#o-grid').onchange = () => view.setGrid($('#o-grid').checked);
$('#o-skel').onchange = () => view.setSkeleton($('#o-skel').checked);
$('#o-bg').oninput = () => { view.setBackground($('#o-bg').value); try { localStorage.setItem('bg', $('#o-bg').value); } catch {} };
$('#b-center').onclick = () => view.frame();
$('#b-shot').onclick = async () => {
  try { const p = await api('save_png', view.snapshot(), `${S.meta?.code || 'dw3'}_${S.motion ?? 0}_${view.frameIndex()}.png`); if (p) toast(t('saved') + ': ' + p); }
  catch (e) { toast(e.message, true); }
};

// ------------------------------------------------------------------ textures / HD
async function applyHd() {
  const maps = {};
  for (const [name, v] of Object.entries(S.hd || {})) maps[Number(name.match(/\d+/)[0])] = v.url;
  await view.setHd(maps);
}
function renderTex() {
  const m = S.meta; if (!m) return;
  $('#texs').innerHTML = m.textures.map(x => {
    const hd = S.hd[x.file];
    return `<div class="tex"><div class="t"><b>${esc(x.file)}</b> <span class="dim">${x.width}×${x.height} · ${esc(x.depth || '')} · tpage ${x.tpage}, CLUT ${x.clut}</span></div>
      <img src="${S.base + x.file}" alt="">
      ${hd ? `<img src="${hd.url}" alt=""><div class="small">${t('hdon')}: ${hd.width}×${hd.height}</div>` : `<div class="small dim">${t('hdoff')}</div>`}
      <div class="row"><button data-hd="${esc(x.file)}">${t('import')}</button>${hd ? `<button data-hdrm="${esc(x.file)}">${t('remove')}</button>` : ''}</div></div>`;
  }).join('');
}
$('#texs').addEventListener('click', async e => {
  const b = e.target.closest('button'); if (!b || !S.meta) return;
  try {
    const r = b.dataset.hd ? await api('hd_import', S.meta.id, b.dataset.hd) : await api('hd_remove', S.meta.id, b.dataset.hdrm);
    if (r) { S.hd = r; renderTex(); await applyHd(); }
  } catch (err) { toast(err.message, true); }
});

// ------------------------------------------------------------------ export
document.querySelectorAll('[data-exp]').forEach(b => b.onclick = async () => {
  if (!S.meta) return toast(t('noselect'), true);
  try {
    const files = await api('export', S.meta.id, b.dataset.exp);
    if (files) { $('#exp-msg').textContent = t('exported', files.length) + ': ' + files.join(', '); toast(t('exported', files.length)); }
  } catch (e) { toast(e.message, true); }
});

// ------------------------------------------------------------------ tabs, start
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tabs button').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('hidden', x.id !== 'tab-' + b.dataset.tab));
  if (b.dataset.tab === 'anim') renderAnims();
});
$('#lang').onchange = () => { lang = $('#lang').value; try { localStorage.setItem('lang', lang); } catch {} applyLang(); };
try { const bg = localStorage.getItem('bg'); if (bg) { $('#o-bg').value = bg; view.setBackground(bg); } } catch {}
applyLang();
window.__viewer.ready = api('app_info').then(info => { window.__viewer.info = info; document.title = `DW3 / DW2003 Viewer ${info.version}`; return info; });
window.__viewer.openDisc = openDisc;
window.__viewer.select = select;
window.__viewer.playMotion = playMotion;
