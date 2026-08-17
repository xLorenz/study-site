/**
 * labeling.js - canonical diagram labeling engine.
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the SVG_MARKUP and LABELS consts at the top.
 * Do not modify the functions below - they are the canonical implementation.
 *
 * Data model (see templates/10-diagram-labeling.md):
 *   SVG_MARKUP: '<svg viewBox="0 0 400 300" ...>...figure with hotspots...</svg>'
 *     Hotspots are any SVG element carrying data-hotspot="h1" (circle, rect,
 *     path, polygon...). The engine finds them, computes their bounding-box
 *     center and places a numbered badge OUTSIDE the shape (right side by
 *     default, flipped when the shape is near an edge) with a leader line.
 *     The figure itself must not contain the label text - the student
 *     supplies it.
 *   LABELS: [{ id:'l1', text:'Nucleo', target:'h1' }]
 *     target = the data-hotspot id the label belongs to (the answer key).
 *
 * Interaction contract:
 *   - Selection is CHIP-FIRST: click a chip to select it (visual feedback),
 *     then click a hotspot to place it there. Clicking a hotspot with no
 *     chip selected shows a nudge hint - hotspots can never be selected
 *     alone. Clicking an assigned chip removes its assignment.
 *   - Placing a label NEVER marks it correct or wrong: neutral accent styling
 *     only. Green/red verdicts appear exclusively on "Comprobar"; "Revelar"
 *     shows the answers in green.
 *   - Label text is drawn beside its badge with a leader line, a dark halo
 *     (paint-order stroke) and a small per-hotspot vertical stagger so
 *     neighbouring labels do not overlap each other or the figure.
 *
 * Required HTML (see templates/10-diagram-labeling.md):
 *   #labelSvg (the SVG is injected here), #labelChips, #labelStatus,
 *   #labelCheck, #labelReveal, #labelReset, #labelScore
 */

const SVG_MARKUP = '<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg"> ... </svg>';

const LABELS = [
  /* Fill me. { id:'l1', text:'...', target:'h1' } - target matches data-hotspot. */
];

/* ---- state ---- */
const state = { chips: [], assignments: {}, selection: null, revealed: false, checked: false, spots: [] };

const $ = (id) => document.getElementById(id);

function shuffle(arr){
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--){
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function setStatus(msg){
  $('labelStatus').textContent = msg;
}

function buildSvg(){
  const host = $('labelSvg');
  host.innerHTML = SVG_MARKUP;
  const svg = host.querySelector('svg');
  if (!svg){
    setStatus('Error: SVG_MARKUP no contiene un elemento <svg>.');
    return null;
  }
  svg.style.width = '100%';
  svg.style.height = 'auto';
  const vb = svg.viewBox && svg.viewBox.baseVal ? svg.viewBox.baseVal : { width: 400, height: 300 };
  const spots = [];
  svg.querySelectorAll('[data-hotspot]').forEach((el, i) => {
    const b = el.getBBox();
    const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
    const pad = 38;
    const cands = [
      { x: b.x + b.width + 16, y: b.y - 2 },
      { x: b.x - 16, y: b.y - 2 },
      { x: b.x + b.width / 2, y: b.y - 16 },
      { x: b.x + b.width / 2, y: b.y + b.height + 16 }
    ];
    let pos = cands[0];
    for (const c of cands){
      if (c.x >= pad && c.x <= vb.width - pad && c.y >= pad && c.y <= vb.height - pad){ pos = c; break; }
    }
    const side = pos.x >= cx ? 'right' : 'left';
    const stagger = ((i % 3) - 1) * 13;
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('data-badge', hotspotId(el));
    g.innerHTML =
      '<line x1="' + pos.x + '" y1="' + pos.y + '" x2="' + cx + '" y2="' + cy + '" stroke="#2a2a3a" stroke-width="1" opacity="0.7"/>' +
      '<circle r="13" fill="#0a0a0f" stroke="var(--accent,#4d70b8)" stroke-width="2"/>' +
      '<text y="4.5" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">' + (i + 1) + '</text>';
    g.setAttribute('transform', 'translate(' + pos.x + ',' + pos.y + ')');
    g.classList.add('badge');
    g.addEventListener('click', () => assignTo(hotspotId(el)));
    svg.appendChild(g);
    spots.push({ id: hotspotId(el), el, badge: g, cx, cy, pos, side, stagger, index: i });
  });
  return spots;
}

function hotspotId(el){
  return el.getAttribute('data-hotspot');
}

function renderChips(){
  const wrap = $('labelChips');
  wrap.innerHTML = '';
  state.chips.forEach(l => {
    const b = document.createElement('button');
    b.className = 'label-chip';
    b.dataset.id = l.id;
    b.innerHTML = l.text;
    const assigned = !!state.assignments[l.target] && state.assignments[l.target] === l.id;
    if (assigned) b.classList.add('assigned');
    if (state.selection && state.selection.id === l.id) b.classList.add('selected');
    if (state.checked){
      if (state.assignments[l.target] === l.id) b.classList.add('ok');
      else b.classList.add('bad');
    }
    if (state.revealed) b.classList.add('revealed');
    b.addEventListener('click', () => pickChip(l));
    wrap.appendChild(b);
  });
  renderMath();
}

function pickChip(l){
  if (state.revealed) return;
  if (state.selection && state.selection.id === l.id){
    state.selection = null;
    setStatus('Selección quitada.');
    renderChips();
    renderSpotState();
    return;
  }
  if (state.assignments[l.target] === l.id){
    unassign(l.target);
    setStatus('Etiqueta quitada: ' + l.text + '.');
    return;
  }
  state.selection = { id: l.id };
  setStatus('Seleccionada: ' + l.text + ' — ahora haz clic en la zona del diagrama.');
  renderChips();
  renderSpotState();
}

function assignTo(spotId){
  if (state.revealed) return;
  const spot = state.spots.find(s => s.id === spotId);
  if (!spot) return;
  if (!state.selection){
    setStatus('Primero elige una etiqueta de la lista.');
    const wrap = $('labelChips');
    wrap.classList.remove('nudge');
    void wrap.offsetWidth;
    wrap.classList.add('nudge');
    return;
  }
  const l = LABELS.find(x => x.id === state.selection.id);
  assign(spotId, l.id);
  state.selection = null;
  setStatus('Colocada: ' + l.text + ' en la zona ' + (spot.index + 1) + '.');
}

function assign(spotId, labelId){
  const l = LABELS.find(x => x.id === labelId);
  state.assignments[spotId] = labelId;
  addTextAt(spotId, l.text, false);
  renderChips();
  renderSpotState();
}

function unassign(spotId){
  delete state.assignments[spotId];
  const old = document.querySelector('[data-answer-text="' + spotId + '"]');
  if (old) old.remove();
  renderChips();
  renderSpotState();
}

function addTextAt(spotId, text, revealed){
  const spot = state.spots.find(s => s.id === spotId);
  if (!spot) return;
  const host = spot.badge;
  const old = host.querySelector('[data-answer-text]');
  if (old) old.remove();
  const side = spot.side;
  const tx = side === 'right' ? 20 : -20;
  const ty = spot.stagger;
  const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  t.setAttribute('data-answer-text', spotId);
  t.setAttribute('x', tx);
  t.setAttribute('y', ty + 4);
  t.setAttribute('text-anchor', side === 'right' ? 'start' : 'end');
  t.setAttribute('font-size', '14');
  t.setAttribute('font-weight', '600');
  t.setAttribute('fill', revealed ? 'var(--green,#4ade80)' : 'var(--secondary,#7a9ed4)');
  t.setAttribute('stroke', '#0a0a0f');
  t.setAttribute('stroke-width', '3');
  t.setAttribute('paint-order', 'stroke');
  t.textContent = text.replace(/\$\$[^$]*?\$\$/g, '').replace(/\$[^$\n]*?\$/g, '').replace(/\\\([^)]*?\\\)/g, '');
  host.appendChild(t);
}

function renderSpotState(){
  state.spots.forEach(spot => {
    spot.badge.classList.toggle('assigned', !!state.assignments[spot.id]);
    spot.badge.classList.toggle('selected', false);
  });
}

function check(){
  if (state.revealed) return;
  state.checked = true;
  let ok = 0;
  LABELS.forEach(l => {
    if (state.assignments[l.target] === l.id) ok++;
  });
  state.spots.forEach(spot => {
    const l = LABELS.find(x => x.target === spot.id);
    const correct = l && state.assignments[spot.id] === l.id;
    spot.badge.classList.toggle('ok', !!correct);
    spot.badge.classList.toggle('bad', !correct);
  });
  $('labelScore').textContent = ok + ' / ' + LABELS.length + ' correctas';
  setStatus(ok === LABELS.length
    ? 'Todo correcto. Diagrama completo.'
    : 'Revisa las marcadas en rojo y vuelve a comprobar.');
  renderChips();
}

function reveal(){
  if (state.revealed) return;
  state.revealed = true;
  LABELS.forEach(l => {
    state.assignments[l.target] = l.id;
    addTextAt(l.target, l.text, true);
  });
  state.spots.forEach(spot => spot.badge.classList.add('revealed'));
  setStatus('Respuestas reveladas.');
  $('labelScore').textContent = LABELS.length + ' / ' + LABELS.length;
  renderChips();
}

function reset(){
  state.assignments = {};
  state.selection = null;
  state.revealed = false;
  state.checked = false;
  state.chips = shuffle(LABELS.slice());
  document.querySelectorAll('[data-answer-text]').forEach(t => t.remove());
  state.spots.forEach(spot => {
    spot.badge.classList.remove('ok', 'bad', 'assigned', 'selected', 'revealed');
  });
  $('labelScore').textContent = '';
  setStatus('Elige una etiqueta y luego haz clic en la zona correspondiente del diagrama.');
  renderChips();
  renderSpotState();
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

document.addEventListener('DOMContentLoaded', () => {
  state.spots = buildSvg() || [];
  $('labelCheck').addEventListener('click', check);
  $('labelReveal').addEventListener('click', reveal);
  $('labelReset').addEventListener('click', reset);
  reset();
  loadKaTeX();
});