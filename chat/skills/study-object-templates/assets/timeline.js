/**
 * timeline.js - canonical interactive timeline engine.
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the EVENTS, ERAS and CATEGORY_COLORS consts at the top.
 * Do not modify the functions below - they are the canonical implementation.
 *
 * Data model (see templates/08-timeline.md):
 *   EVENTS: [{ id:'e1', year:1905, era:'mecanica', eraLabel:'Mecanica',
 *              cat:'concepto', title:'...', summary:'1 sentence',
 *              detail:'<p>HTML expansion shown in the detail panel</p>' }]
 *   ERAS:   [{ key:'mecanica', label:'Mecanica' }]  (ordered, oldest first)
 *   CATEGORY_COLORS: { concepto:'#5b7fc4', ... }  (one entry per cat used)
 *
 * Layout contract:
 *   - Left rail: a floating panel pinned to the viewport (it never scrolls
 *     with the page). Its vertical line is color-coded by ERA (topic): one
 *     colored segment per era spanning the year range of its events. An
 *     axis of ROUNDED years runs beside the line (steps of 1/2/5 x 10^k
 *     chosen from the span, ~6 divisions) with small horizontal ticks
 *     crossing the line; event years are shown per dot to the right of the
 *     line.
 *     One dot per event sits at its proportional year position; events that
 *     share the same year are CLUSTERED: the dots fan out horizontally so
 *     they never overlap each other. A year label sits to the RIGHT of each
 *     dot (one label per cluster).
 *   - Right list: every event as a row (year, era chip, title, summary);
 *     the list scrolls with the page while the rail stays floating.
 *   - Filters: era buttons + category buttons + free-text search. All
 *     three combine; the rail and list always show the same filtered set.
 *   - Detail panel: modal overlay (#detailPanel) with title, chips, year
 *     and HTML body. Escape or the close button dismisses it.
 *
 * Required HTML (see templates/08-timeline.md):
 *   #eraFilters, #catFilters, #tlSearch, #tlCount,
 *   #tlRail, #tlList,
 *   #detailOverlay, #detailPanel (#detailTitle, #detailChips, #detailYear, #detailBody, #detailClose),
 *   #tlReset
 */

const EVENTS = [
  /* Fill me. One entry per event. Order within the same year is preserved. */
];

/* Ordered oldest-first; every e.era must exist here. */
const ERAS = [];

/* Keys must match every e.cat. Pull hues from the subject theme. */
const CATEGORY_COLORS = {};

/* ---- state ---- */
const state = { era: 'all', cat: 'all', query: '', selected: null, filtered: [] };

const $ = (id) => document.getElementById(id);

function byYear(a, b){ return a.year - b.year || 0; }

function norm(s){ return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }

function filterEvents(){
  state.filtered = EVENTS.filter(e =>
    (state.era === 'all' || e.era === state.era) &&
    (state.cat === 'all' || e.cat === state.cat) &&
    (state.query === '' ||
      norm(e.title + ' ' + e.summary + ' ' + e.eraLabel).includes(state.query))
  ).sort(byYear);
  $('tlCount').textContent = state.filtered.length + ' / ' + EVENTS.length + ' eventos';
}

/* ---- filter bar ---- */
function buildFilters(){
  const eraBar = $('eraFilters');
  eraBar.innerHTML = '';
  const allEra = document.createElement('button');
  allEra.className = 'filter-btn active';
  allEra.dataset.k = 'all';
  allEra.textContent = 'Todos';
  eraBar.appendChild(allEra);
  ERAS.forEach(era => {
    const b = document.createElement('button');
    b.className = 'filter-btn';
    b.dataset.k = era.key;
    b.textContent = era.label;
    eraBar.appendChild(b);
  });
  eraBar.querySelectorAll('.filter-btn').forEach(b => {
    b.addEventListener('click', () => {
      eraBar.querySelectorAll('.filter-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      state.era = b.dataset.k;
      render();
    });
  });

  const catBar = $('catFilters');
  catBar.innerHTML = '';
  const allCat = document.createElement('button');
  allCat.className = 'filter-btn active';
  allCat.dataset.k = 'all';
  allCat.textContent = 'Todas';
  catBar.appendChild(allCat);
  Object.keys(CATEGORY_COLORS).forEach(key => {
    const b = document.createElement('button');
    b.className = 'filter-btn';
    b.dataset.k = key;
    b.style.setProperty('--fc', CATEGORY_COLORS[key]);
    b.textContent = key;
    catBar.appendChild(b);
  });
  catBar.querySelectorAll('.filter-btn').forEach(b => {
    b.addEventListener('click', () => {
      catBar.querySelectorAll('.filter-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      state.cat = b.dataset.k;
      render();
    });
  });
}

/* ---- rail ---- */
function niceStep(range){
  const raw = Math.max(range, 1) / 6;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  let step = 1;
  if (norm > 1 && norm <= 2) step = 2;
  else if (norm > 2 && norm <= 5) step = 5;
  else if (norm > 5) step = 10;
  return step * mag;
}

function buildRail(){
  const rail = $('tlRail');
  rail.innerHTML = '';
  const ev = state.filtered;
  if (ev.length === 0){ return; }
  const min = ev[0].year, max = ev[ev.length - 1].year;
  const span = Math.max(max - min, 1);
  const yPct = (year) => 8 + ((year - min) / span) * 84;

  const eraColors = Object.values(CATEGORY_COLORS);
  ERAS.forEach((era, i) => {
    const inEra = ev.filter(e => e.era === era.key);
    if (inEra.length === 0){ return; }
    const top = yPct(inEra[0].year);
    const bottom = yPct(inEra[inEra.length - 1].year);
    const seg = document.createElement('div');
    seg.className = 'tl-seg';
    seg.style.top = top + '%';
    seg.style.height = Math.max(bottom - top, 1.5) + '%';
    const c = (era.color && era.color.charAt(0) === '#') ? era.color : eraColors[i % eraColors.length] || '#5b7fc4';
    seg.style.background = c;
    rail.appendChild(seg);
  });

  if (span > 1){
    const step = niceStep(span);
    for (let y = Math.floor(min / step) * step; y <= Math.ceil(max / step) * step; y += step){
      const pct = Math.min(97, Math.max(3, yPct(y)));
      const tick = document.createElement('div');
      tick.className = 'tl-tick';
      tick.style.top = 'calc(' + pct + '% - 1px)';
      rail.appendChild(tick);
      const lb = document.createElement('span');
      lb.className = 'tl-axis-label';
      lb.textContent = y;
      lb.style.top = 'calc(' + pct + '% - 5px)';
      rail.appendChild(lb);
    }
  }

  const byYearMap = {};
  ev.forEach((e, idx) => {
    (byYearMap[e.year] = byYearMap[e.year] || []).push(idx);
  });

  ev.forEach((e, idx) => {
    const pct = yPct(e.year);
    const cluster = byYearMap[e.year];
    const posInCluster = cluster.indexOf(idx);
    const fan = cluster.length > 1 ? Math.max(-18, 6 * posInCluster) : 0;
    const dot = document.createElement('button');
    dot.className = 'tl-dot' + (cluster.length > 1 ? ' clustered' : '');
    dot.style.top = 'calc(' + pct + '% - 6px)';
    dot.style.left = 'calc(32px + ' + fan + 'px)';
    dot.style.setProperty('--c', CATEGORY_COLORS[e.cat] || '#5b7fc4');
    dot.title = e.year + ' - ' + e.title;
    dot.dataset.id = e.id;
    dot.setAttribute('aria-label', e.year + ', ' + e.title);
    dot.addEventListener('click', () => openDetail(e));
    rail.appendChild(dot);
    if (posInCluster === 0){
      const label = document.createElement('span');
      label.className = 'tl-year-label';
      label.textContent = e.year;
      label.style.top = 'calc(' + pct + '% - 6px)';
      rail.appendChild(label);
    }
  });

  const labels = Array.from(rail.querySelectorAll('.tl-year-label'));
  const h = rail.clientHeight;
  const nat = labels.map(lb => {
    const pct = parseFloat(lb.style.top.replace('calc(', '')) || 0;
    return (pct / 100) * h - 6;
  });
  const top = nat.slice();
  for (let pass = 0; pass < labels.length + 2; pass++){
    let changed = false;
    for (let i = 1; i < top.length; i++){
      const minTop = top[i - 1] + 24;
      if (top[i] < minTop){ top[i] = minTop; changed = true; }
    }
    for (let i = top.length - 2; i >= 0; i--){
      const maxTop = top[i + 1] - 24;
      if (top[i] > maxTop){ top[i] = Math.max(nat[i], maxTop); changed = true; }
    }
    if (!changed) break;
  }
  labels.forEach((lb, i) => { lb.style.top = top[i] + 'px'; });
}

/* ---- list ---- */
function buildList(){
  const list = $('tlList');
  list.innerHTML = '';
  if (state.filtered.length === 0){
    list.innerHTML = '<div class="tl-empty">No hay eventos que coincidan con los filtros.</div>';
    return;
  }
  state.filtered.forEach(e => {
    const row = document.createElement('article');
    row.className = 'tl-row';
    row.dataset.id = e.id;
    row.style.setProperty('--c', CATEGORY_COLORS[e.cat] || '#5b7fc4');
    row.innerHTML =
      '<div class="tl-year">' + e.year + '</div>' +
      '<div class="tl-row-main">' +
        '<div class="tl-row-top">' +
          '<span class="badge" style="--c:' + (CATEGORY_COLORS[e.cat] || '#5b7fc4') + '">' + e.cat + '</span>' +
          '<span class="tl-era-chip">' + e.eraLabel + '</span>' +
        '</div>' +
        '<h3 class="tl-title">' + e.title + '</h3>' +
        '<p class="tl-summary">' + e.summary + '</p>' +
      '</div>';
    row.addEventListener('click', () => openDetail(e));
    row.addEventListener('mouseenter', () => highlight(e.id, true));
    row.addEventListener('mouseleave', () => highlight(e.id, false));
    list.appendChild(row);
  });
}

function highlight(id, on){
  const dot = document.querySelector('.tl-dot[data-id="' + id + '"]');
  const row = document.querySelector('.tl-row[data-id="' + id + '"]');
  if (dot) dot.classList.toggle('hover', on);
  if (row) row.classList.toggle('hover', on);
}

/* ---- detail panel ---- */
function openDetail(e){
  state.selected = e.id;
  $('detailTitle').textContent = e.title;
  $('detailYear').textContent = e.year;
  $('detailChips').innerHTML =
    '<span class="badge" style="--c:' + (CATEGORY_COLORS[e.cat] || '#5b7fc4') + '">' + e.cat + '</span>' +
    '<span class="tl-era-chip">' + e.eraLabel + '</span>';
  $('detailBody').innerHTML = e.detail || '<p class="muted">Sin detalle adicional.</p>';
  renderMath();
  $('detailOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  $('detailClose').focus();
}

function closeDetail(){
  $('detailOverlay').classList.remove('open');
  document.body.style.overflow = '';
}

/* ---- render ---- */
function render(){
  filterEvents();
  buildRail();
  buildList();
  if (state.selected && !state.filtered.some(e => e.id === state.selected)) state.selected = null;
  renderMath();
}

/* ---- Math: KaTeX with unicode fallback (canonical) ---- */
function renderMath(){
  if (window.renderMathInElement){
    try {
      renderMathInElement(document.body, {
        delimiters: [
          { left: '$$', right: '$$', display: false },
          { left: '$', right: '$', display: false },
          { left: '\\(', right: '\\)', display: false }
        ],
        throwOnError: false
      });
      document.querySelectorAll('.formula,.cc-formula,.code-block').forEach(el => {
        if (el.querySelector('.katex')){
          let seen = false;
          el.childNodes.forEach(n => {
            if (n.nodeType === 3){ if (seen) n.nodeValue = ''; }
            else if (n.nodeType === 1 && (n.classList.contains('katex') || n.querySelector('.katex'))) seen = true;
          });
        }
      });
      return;
    } catch (e){}
  }
  if (!katexTried) return;
  stripMathMarkers();
}

function stripMathMarkers(){
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(n => {
    if (n.parentElement && (n.parentElement.tagName === 'SCRIPT' || n.parentElement.tagName === 'STYLE')) return;
    const t = n.nodeValue;
    if (t.indexOf('$') !== -1) n.nodeValue = t.replace(/\$\$[^$]*?\$\$/g, '').replace(/\$[^$\n]*?\$/g, '').replace(/\\\([^)]*?\\\)/g, '');
  });
}

let katexTried = false;
const KATEX_CDNS = [
  { css: 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css', js: 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js', auto: 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js' },
  { css: 'https://unpkg.com/katex@0.16.11/dist/katex.min.css', js: 'https://unpkg.com/katex@0.16.11/dist/katex.min.js', auto: 'https://unpkg.com/katex@0.16.11/dist/contrib/auto-render.min.js' },
  { css: 'https://cdnjs.cloudflare.com/ajax/libs/katex/0.16.11/katex.min.css', js: 'https://cdnjs.cloudflare.com/ajax/libs/katex/0.16.11/katex.min.js', auto: 'https://cdnjs.cloudflare.com/ajax/libs/katex/0.16.11/contrib/auto-render.min.js' }
];
let katexCdnIdx = 0;
function loadKaTeX(){
  if (katexTried) return;
  katexTried = true;
  const cdn = KATEX_CDNS[katexCdnIdx];
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = cdn.css;
  document.head.appendChild(css);
  let remaining = 2;
  let failed = false;
  const done = () => {
    remaining--;
    if (remaining === 0 && !failed){ renderMath(); }
    else if (failed) tryNext();
  };
  const fail = () => { failed = true; tryNext(); };
  const tryNext = () => {
    if (katexCdnIdx + 1 < KATEX_CDNS.length){
      katexCdnIdx++;
      katexTried = false;
      loadKaTeX();
    } else {
      renderMath();
    }
  };
  const main = document.createElement('script');
  main.src = cdn.js;
  main.onload = done;
  main.onerror = fail;
  document.head.appendChild(main);
  const auto = document.createElement('script');
  auto.src = cdn.auto;
  auto.onload = done;
  auto.onerror = fail;
  document.head.appendChild(auto);
  setTimeout(() => { if (!window.renderMathInElement){ failed = true; tryNext(); } }, 5000);
  setTimeout(() => { if (!window.renderMathInElement) stripMathMarkers(); }, 6000);
}

/* ---- init ---- */
document.addEventListener('DOMContentLoaded', () => {
  buildFilters();
  $('tlSearch').addEventListener('input', (e) => { state.query = e.target.value.trim(); render(); });
  $('tlReset').addEventListener('click', () => {
    state.era = 'all'; state.cat = 'all'; state.query = '';
    $('tlSearch').value = '';
    document.querySelectorAll('#eraFilters .filter-btn, #catFilters .filter-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.k === 'all');
    });
    render();
  });
  $('detailClose').addEventListener('click', closeDetail);
  $('detailOverlay').addEventListener('click', (e) => { if (e.target === $('detailOverlay')) closeDetail(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && $('detailOverlay').classList.contains('open')) closeDetail();
  });
  render();
  loadKaTeX();
});