/**
 * cheat-sheet.js — canonical interactive cheat sheet engine.
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the CARDS and TOPIC_COLORS consts at the top.
 * Do not modify the functions below — they are the canonical implementation.
 *
 * Card model (see templates/05-cheat-sheet.md):
 *   { id:'c1', cat:'topic-key', catLabel:'Topic', kind:'concept'|'formula',
 *     title:'...', summary:'1-2 sentences',
 *     formula:'$$...$$ unicode fallback',   // required when kind==='formula'
 *     detail:'<p>HTML explanation…</p>' }
 *
 * Rules enforced here:
 *   - Every card belongs to its topic (cat) and is color-coded by it.
 *   - Cards with kind==='formula' ALSO appear under the formulas-only toggle
 *     (theorems / formulas / equations / constants are a cross-topic category).
 *   - Closed cards show only the title + badges; the summary, formula and
 *     detail live in the body and are revealed when opened.
*  - The click target is the card HEADER only, so the body text stays
 *     selectable. Cards expand in-flow inside their own FIXED column
 *     (cascade): opening a card only pushes the cards below it in that
 *     column — the rest of the sheet never moves, columns never rebalance.
 *   - KaTeX is loaded from CDN to render $$...$$ delimiters; if it fails to
 *     load, the delimiters are stripped and the unicode content is shown.
 *
 * Required HTML (see templates/05-cheat-sheet.md):
 *   #catFilters, #formulaToggle, #cheatSearch, #resultCount, #cardGrid
 */

const CARDS = [
  /* Fill me. One card per concept. At least 15-30 cards for a full cheat sheet. */
];

/* Keys must match every q.cat. Pull hues from the subject theme. */
const TOPIC_COLORS = {};

const KIND_LABEL = 'fórmula';

/* ── State ── */
const state = { cat: 'all', formulasOnly: false, query: '' };

/* ── Filter bar ── */
function buildFilters(){
  const cats = [];
  CARDS.forEach(c => { if (!cats.some(x => x.key === c.cat)) cats.push({ key: c.cat, label: c.catLabel }); });
  const bar = document.getElementById('catFilters');
  bar.innerHTML = '';
  const allBtn = document.createElement('button');
  allBtn.className = 'filter-btn' + (state.cat === 'all' ? ' active' : '');
  allBtn.textContent = 'Todos';
  allBtn.addEventListener('click', () => { state.cat = 'all'; render(); });
  bar.appendChild(allBtn);
  cats.forEach(c => {
    const btn = document.createElement('button');
    btn.className = 'filter-btn' + (state.cat === c.key ? ' active' : '');
    btn.style.setProperty('--fc', TOPIC_COLORS[c.key]);
    btn.textContent = c.label;
    btn.addEventListener('click', () => { state.cat = c.key; render(); });
    bar.appendChild(btn);
  });
  const toggle = document.getElementById('formulaToggle');
  toggle.addEventListener('change', () => { state.formulasOnly = toggle.checked; render(); });
}

/* ── Filtering ── */
function visibleCards(){
  const q = state.query.toLowerCase();
  return CARDS.filter(c => {
    if (state.cat !== 'all' && c.cat !== state.cat) return false;
    if (state.formulasOnly && c.kind !== 'formula') return false;
    if (q){
      const hay = (c.title + ' ' + c.summary + ' ' + (c.formula || '') + ' ' + (c.detail || '')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

/* ── Render ── */
function render(){
  const cards = visibleCards();
  const grid = document.getElementById('cardGrid');
  grid.innerHTML = '';
  document.getElementById('resultCount').textContent = cards.length + ' de ' + CARDS.length + ' tarjetas';

  /* FIXED columns: cards are assigned to a column once per render, in
     reading order (row-major). The number of columns depends only on the
     container width — it never changes when a card opens, and columns are
     never rebalanced: opening a card only pushes the cards below it in its
     own column (cascade). */
  const numCols = Math.max(1, Math.min(4, Math.floor(grid.clientWidth / 340)));
  grid.style.setProperty('--cols', numCols);
  const cols = [];
  for (let j = 0; j < numCols; j++){
    const col = document.createElement('div');
    col.className = 'cc-col';
    grid.appendChild(col);
    cols.push(col);
  }

  cards.forEach((c, i) => {
    const col = cols[i % numCols];

    const card = document.createElement('div');
    card.className = 'cheat-card';
    card.style.setProperty('--fc', TOPIC_COLORS[c.cat] || '#6a6a7a');
    card.style.animationDelay = (i * 40) + 'ms';

    let html = '<div class="cc-header" tabindex="0" role="button" aria-expanded="false">'
      + '<div class="cc-top">'
      + '<span class="cc-badge" style="background:' + (TOPIC_COLORS[c.cat] || '#6a6a7a') + '">' + c.catLabel + '</span>'
      + (c.kind === 'formula' ? '<span class="cc-badge kind">' + KIND_LABEL + '</span>' : '')
      + '</div>'
      + '<h3 class="cc-title">' + c.title + '</h3>'
      + '<span class="cc-hint">+</span>'
      + '</div>'
      + '<div class="cc-body">'
      + '<p class="cc-summary">' + c.summary + '</p>';
    if (c.formula){
      html += '<div class="cc-formula">' + c.formula + '</div>';
    }
    if (c.detail){
      html += '<div class="cc-detail">' + c.detail + '</div>';
    }
    html += '</div>';
    card.innerHTML = html;

    const header = card.querySelector('.cc-header');
    header.addEventListener('click', () => {
      card.classList.toggle('open');
      header.setAttribute('aria-expanded', card.classList.contains('open') ? 'true' : 'false');
    });
    header.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' '){
        e.preventDefault();
        card.classList.toggle('open');
        header.setAttribute('aria-expanded', card.classList.contains('open') ? 'true' : 'false');
      }
    });

    col.appendChild(card);
  });

  renderMath();
}

/* ── Math: KaTeX with unicode fallback ── */
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
    } catch (e){ /* fall through to unicode fallback */ }
  }
  /* KaTeX unavailable — drop the $$…$$ LaTeX blocks entirely and keep the
     unicode content that follows them (raw \frac would be unreadable). */
  document.querySelectorAll('.cc-formula').forEach(el => {
    el.innerHTML = el.innerHTML.replace(/\$\$[^$]*?\$\$/g, '').replace(/\$[^$\n]*?\$/g, '').replace(/\\\([^)]*?\\\)/g, '');
  });
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
  /* Safety: never leave formulas unrendered — fallback after 5s */
  setTimeout(() => { if (!window.renderMathInElement){ failed = true; tryNext(); } }, 5000);
  setTimeout(() => { if (!window.renderMathInElement) stripMathMarkers(); }, 6000);
}

/* ── Events ── */
document.getElementById('cheatSearch').addEventListener('input', e => {
  state.query = e.target.value;
  render();
});
document.getElementById('clearSearch').addEventListener('click', () => {
  document.getElementById('cheatSearch').value = '';
  state.query = '';
  render();
  document.getElementById('cheatSearch').focus();
});

/* ── Go ── */
buildFilters();
render();
loadKaTeX();