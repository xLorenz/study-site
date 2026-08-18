/**
 * matching.js - canonical matching game engine (terms <-> definitions).
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the PAIRS and PAIR_COLORS consts at the top.
 * Do not modify the functions below - they are the canonical implementation.
 *
 * Data model (see templates/09-matching-game.md):
 *   PAIRS: [{ id:'p1', term:'<b>Masa</b>', def:'...' }]
 *   PAIR_COLORS: {}  (optional; a color per pair id, e.g. for subtle hints)
 *
 * Rules enforced here:
 *   - Left column holds the terms, right column the definitions; each side
 *     is shuffled independently at start and on restart.
 *   - Click any card to select it (either column), click a card on the
 *     OPPOSITE column to attempt a match. Clicking the SAME selected card
 *     again deselects it (toggle). Clicking another card on the same column
 *     moves the selection.
 *   - Correct pairs lock in place (green + check). A wrong attempt flashes
 *     red ONLY the card that was just clicked - the selected card stays
 *     selected so you can retry, and no other card is ever touched. The
 *     error counter increments per wrong attempt.
 *   - Win state: all pairs matched -> summary card with moves, errors and
 *     a restart button.
 *   - Keyboard: every card is a <button>; Enter/Space selects and matches.
 *
 * Required HTML (see templates/09-matching-game.md):
 *   #matchLeft, #matchRight, #matchStatus (aria-live),
 *   #matchMoves, #matchErrors, #matchReset, #matchWrap, #matchSummary
 */

const PAIRS = [
  /* Fill me. { id:'p1', term:'...', def:'...' } - at least 6 pairs, max ~14 */
];

/* Optional per-pair accent color (keyed by pair id). Leave empty to use the theme accent. */
const PAIR_COLORS = {};

/* ---- state ---- */
const state = { left: [], right: [], selected: null, matched: new Set(), moves: 0, errors: 0, flashTimer: null };

const $ = (id) => document.getElementById(id);

function shuffle(arr){
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--){
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function clearSelection(){
  document.querySelectorAll('.match-card.selected').forEach(b => b.classList.remove('selected'));
  state.selected = null;
}

function cardHTML(pair, side){
  const color = PAIR_COLORS[pair.id] || '';
  return '<button class="match-card" data-id="' + pair.id + '" data-side="' + side + '"' +
    (color ? ' style="--pc:' + color + '"' : '') + '>' +
    (side === 'left' ? pair.term : pair.def) + '</button>';
}

function renderColumns(){
  const L = $('matchLeft'), R = $('matchRight');
  L.innerHTML = state.left.map(p => cardHTML(p, 'left')).join('');
  R.innerHTML = state.right.map(p => cardHTML(p, 'right')).join('');
  document.querySelectorAll('.match-card').forEach(btn => {
    btn.addEventListener('click', () => pick(btn));
  });
  renderMath();
}

function pick(btn){
  const id = btn.dataset.id, side = btn.dataset.side;
  if (state.matched.has(id)) return;

  if (state.selected && state.selected.id === id && state.selected.side === side){
    clearSelection();
    $('matchStatus').textContent = 'Selección quitada.';
    return;
  }

  if (!state.selected || state.selected.side === side){
    clearSelection();
    state.selected = { id, side };
    btn.classList.add('selected');
    $('matchStatus').textContent = 'Seleccionado. Elige su pareja en la otra columna (o pulsa de nuevo para quitar).';
    return;
  }

  state.moves++;
  $('matchMoves').textContent = state.moves;

  if (state.selected.id === id){
    state.matched.add(id);
    state.selected = null;
    clearSelection();
    const cards = document.querySelectorAll('.match-card[data-id="' + id + '"]');
    cards.forEach(c => { c.classList.add('matched'); c.disabled = true; });
    $('matchStatus').textContent = 'Pareja correcta: ' + state.matched.size + ' de ' + PAIRS.length;
    if (state.matched.size === PAIRS.length) win();
  } else {
    state.errors++;
    $('matchErrors').textContent = state.errors;
    if (state.flashTimer) clearTimeout(state.flashTimer);
    btn.classList.add('wrong');
    state.flashTimer = setTimeout(() => {
      btn.classList.remove('wrong');
      state.flashTimer = null;
    }, 700);
    $('matchStatus').textContent = 'No coincide, intenta de nuevo.';
  }
}

function win(){
  $('matchStatus').textContent = 'Completado: todas las parejas emparejadas.';
  $('matchSummary').classList.remove('hidden');
  $('matchSummary').innerHTML =
    '<h2>Par finalizado</h2>' +
    '<p>Parejas: ' + PAIRS.length + ' · Intentos: ' + state.moves +
    ' · Errores: ' + state.errors + '</p>' +
    '<button class="btn-primary" id="matchAgain">Jugar de nuevo</button>';
  $('matchAgain').addEventListener('click', reset);
  $('matchSummary').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function reset(){
  if (state.flashTimer) clearTimeout(state.flashTimer);
  state.left = shuffle(PAIRS.map(p => p));
  state.right = shuffle(PAIRS.map(p => p));
  state.selected = null;
  state.matched = new Set();
  state.moves = 0;
  state.errors = 0;
  $('matchMoves').textContent = '0';
  $('matchErrors').textContent = '0';
  $('matchStatus').textContent = 'Empareja cada término con su definición.';
  $('matchSummary').classList.add('hidden');
  renderColumns();
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

document.addEventListener('DOMContentLoaded', () => {
  $('matchReset').addEventListener('click', reset);
  reset();
  loadKaTeX();
});