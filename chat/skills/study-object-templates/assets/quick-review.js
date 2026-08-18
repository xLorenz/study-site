/**
 * quick-review.js - canonical quick review engine (concept categorization).
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the DECK and TOPIC_COLORS consts at the top.
 * Do not modify the functions below - they are the canonical implementation.
 *
 * Data model (see templates/12-quick-review.md):
 *   DECK: [{ id:'d1', topic:'cinematica', topicLabel:'Cinematica',
 *            front:'<b>Formula de MRUV?</b>', back:'<p>$$v = v_0 + a t$$ v = v0 + a·t</p>',
 *            hint:'<p>Empieza por v0...</p>' (optional, empty string = none) }]
 *   TOPIC_COLORS: { cinematica:'#5b7fc4', ... }
 *
 * Interaction contract:
 *   - Quick review: every card is presented once (shuffled). Flip it, then
 *     categorize it with one of the four fixed grades:
 *       Logrado (green) -> Casi (blue) -> Necesita trabajo (yellow) -> Otra vez (red)
 *   - End screen: per-category breakdown with colored bars, a "Repasar los
 *     difíciles" button that starts a focused pass with ONLY the weak cards
 *     (Otra vez first, then Necesita trabajo, then Casi), a "Ver lista"
 *     panel listing every concept with its color tag, and a reset button.
 *   - The weak pass behaves like a normal run: each weak card is presented
 *     once and graded with 1-4. When the pass ends, the summary appears
 *     again; any card still not Logrado stays in the pool and can be
 *     reviewed again with the same button. Rounds repeat until everything
 *     is Logrado.
 *   - Keyboard: Space/Enter flips, 1-4 grades.
 *
 * Required HTML (see templates/12-quick-review.md):
 *   #qrCard, #qrFront, #qrBack, #qrHint,
 *   #qrFlip, #qrGrades (4 buttons, data-cat), #qrReviewed,
 *   #qrCounts (#qrDone, #qrAlmost, #qrNeeds, #qrAgain),
 *   #qrSummary (#qrSummaryBody, #qrWeakBtn, #qrListBtn, #qrResetBtn),
 *   #qrListPanel (#qrList, #qrListClose), #qrReset, #qrWeakBadge
 */

const DECK = [
  /* Fill me. { id:'d1', topic:'...', topicLabel:'...', front:'...', back:'...', hint:'' } */
];

/* Keys must match every d.topic. Pull hues from the subject theme. */
const TOPIC_COLORS = {};

/* Fixed grading categories - do not rename, the UI depends on these keys/colors. */
const CATEGORIES = [
  { key: 'done',   label: 'Logrado',            color: '#4ade80' },
  { key: 'almost', label: 'Casi',               color: '#60a5fa' },
  { key: 'needs',  label: 'Necesita trabajo',   color: '#fbbf24' },
  { key: 'again',  label: 'Otra vez',           color: '#f87171' }
];
const CAT_INDEX = { done: 0, almost: 1, needs: 2, again: 3 };

/* ---- state ---- */
const state = { queue: [], weakPass: false, current: null, flipped: false, cats: {} };

const $ = (id) => document.getElementById(id);

function shuffle(arr){
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--){
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function catOf(id){
  return state.cats[id] || 'done';
}

function counts(){
  const c = { done: 0, almost: 0, needs: 0, again: 0 };
  DECK.forEach(d => { c[catOf(d.id)]++; });
  return c;
}

function renderHeader(){
  const c = counts();
  $('qrReviewed').textContent = Object.keys(state.cats).length + ' / ' + DECK.length;
  $('qrDone').textContent = c.done;
  $('qrAlmost').textContent = c.almost;
  $('qrNeeds').textContent = c.needs;
  $('qrAgain').textContent = c.again;
  $('qrWeakBadge').classList.toggle('hidden', !state.weakPass);
}

function renderCard(){
  renderHeader();
  if (state.queue.length === 0){
    if (state.weakPass) finishWeak();
    else finishReview();
    return;
  }
  state.current = state.queue[0];
  state.flipped = false;
  const card = $('qrCard');
  card.classList.remove('flipped', 'hidden');
  const d = DECK.find(x => x.id === state.current);
  card.style.setProperty('--tc', TOPIC_COLORS[d.topic] || '#5b7fc4');
  $('qrFront').innerHTML = '<span class="badge" style="--c:' + (TOPIC_COLORS[d.topic] || '#5b7fc4') + '">' + d.topicLabel + '</span>' + d.front;
  $('qrBack').innerHTML = d.back;
  $('qrHint').innerHTML = d.hint || '';
  $('qrHint').classList.toggle('hidden', !d.hint);
  $('qrFlip').classList.remove('hidden');
  $('qrGrades').classList.add('hidden');
  $('qrSummary').classList.add('hidden');
  $('qrListPanel').classList.add('hidden');
  renderMath();
}

function flip(){
  if (state.queue.length === 0 || state.flipped) return;
  state.flipped = true;
  $('qrCard').classList.add('flipped');
  $('qrFlip').classList.add('hidden');
  $('qrGrades').classList.remove('hidden');
  renderMath();
}

function grade(cat){
  if (!state.flipped) return;
  const id = state.current;
  state.cats[id] = cat;
  state.queue.shift();
  state.flipped = false;
  renderCard();
}

function catBarsHTML(){
  const c = counts();
  return CATEGORIES.map(cat => {
    const n = c[cat.key];
    const pct = DECK.length ? Math.round((n / DECK.length) * 100) : 0;
    return '<div class="cat-bar-row">' +
      '<span class="cat-dot" style="background:' + cat.color + '"></span>' +
      '<span class="cat-name">' + cat.label + '</span>' +
      '<div class="cat-track"><div class="cat-fill" style="width:' + pct + '%;background:' + cat.color + '"></div></div>' +
      '<span class="cat-num">' + n + '</span>' +
    '</div>';
  }).join('');
}

function weakCount(){
  const c = counts();
  return c.again + c.needs + c.almost;
}

function finishReview(){
  $('qrCard').classList.add('hidden');
  const sum = $('qrSummary');
  sum.classList.remove('hidden');
  const w = weakCount();
  $('qrSummaryBody').innerHTML =
    '<h2>Revisión completada</h2>' +
    '<p class="muted">' + DECK.length + ' conceptos categorizados.</p>' +
    '<div class="cat-bars">' + catBarsHTML() + '</div>' +
    (w
      ? '<p class="weak-msg">' + w + ' concepto' + (w === 1 ? '' : 's') + ' para repasar.</p>'
      : '<p class="weak-msg all-good">¡Todo logrado! No hay conceptos pendientes.</p>');
  $('qrWeakBtn').classList.toggle('hidden', w === 0);
  $('qrWeakBtn').textContent = 'Repasar los difíciles (' + w + ')';
  sum.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function startWeakPass(){
  const c = counts();
  const ids = [].concat(
    shuffle(DECK.filter(d => catOf(d.id) === 'again').map(d => d.id)),
    shuffle(DECK.filter(d => catOf(d.id) === 'needs').map(d => d.id)),
    shuffle(DECK.filter(d => catOf(d.id) === 'almost').map(d => d.id))
  );
  state.weakPass = true;
  state.queue = ids;
  renderCard();
  void c;
}

function finishWeak(){
  $('qrCard').classList.add('hidden');
  state.weakPass = false;
  renderHeader();
  const sum = $('qrSummary');
  sum.classList.remove('hidden');
  const w = weakCount();
  $('qrSummaryBody').innerHTML =
    '<h2>Repaso de los difíciles finalizado</h2>' +
    '<div class="cat-bars">' + catBarsHTML() + '</div>' +
    (w
      ? '<p class="weak-msg">Quedan ' + w + ' concepto' + (w === 1 ? '' : 's') + ' sin lograr — pulsa el botón para repasarlos de nuevo.</p>'
      : '<p class="weak-msg all-good">¡Todos los conceptos difíciles quedaron logrados!</p>');
  $('qrWeakBtn').classList.toggle('hidden', w === 0);
  $('qrWeakBtn').textContent = 'Repasar los difíciles (' + w + ')';
  sum.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function openList(){
  $('qrListPanel').classList.remove('hidden');
  const wrap = $('qrList');
  wrap.innerHTML = '';
  CATEGORIES.forEach(cat => {
    const ids = DECK.filter(d => catOf(d.id) === cat.key).map(d => d.id);
    if (ids.length === 0) return;
    const sec = document.createElement('section');
    sec.className = 'list-section';
    sec.innerHTML =
      '<h3 class="list-sec-title"><span class="cat-dot" style="background:' + cat.color + '"></span>' + cat.label +
      ' <span class="list-sec-count">' + ids.length + '</span></h3>';
    const list = document.createElement('div');
    list.className = 'list-items';
    ids.forEach(id => {
      const d = DECK.find(x => x.id === id);
      const item = document.createElement('article');
      item.className = 'list-item';
      item.style.setProperty('--ic', cat.color);
      item.innerHTML =
        '<div class="list-item-head">' +
          '<span class="badge" style="--c:' + (TOPIC_COLORS[d.topic] || '#5b7fc4') + '">' + d.topicLabel + '</span>' +
          '<span class="list-item-front">' + d.front + '</span>' +
          '<button class="list-reveal">Ver respuesta</button>' +
        '</div>' +
        '<div class="list-item-back" hidden>' + d.back + '</div>';
      item.querySelector('.list-reveal').addEventListener('click', () => {
        const back = item.querySelector('.list-item-back');
        const open = back.hidden;
        back.hidden = !open;
        item.querySelector('.list-reveal').textContent = open ? 'Ocultar respuesta' : 'Ver respuesta';
        if (open) renderMath();
      });
      list.appendChild(item);
    });
    sec.appendChild(list);
    wrap.appendChild(sec);
  });
  if (!wrap.innerHTML){
    wrap.innerHTML = '<p class="muted">No hay conceptos en ninguna categoría.</p>';
  }
  renderMath();
}

function reset(){
  state.queue = shuffle(DECK.map(d => d.id));
  state.weakPass = false;
  state.current = null;
  state.flipped = false;
  state.cats = {};
  $('qrCard').classList.add('hidden');
  $('qrSummary').classList.add('hidden');
  $('qrListPanel').classList.add('hidden');
  renderCard();
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
  $('qrFlip').addEventListener('click', flip);
  $('qrGrades').querySelectorAll('button').forEach(b => {
    b.addEventListener('click', () => grade(b.dataset.cat));
  });
  $('qrWeakBtn').addEventListener('click', startWeakPass);
  $('qrListBtn').addEventListener('click', openList);
  $('qrListClose').addEventListener('click', () => $('qrListPanel').classList.add('hidden'));
  $('qrReset').addEventListener('click', reset);
  document.addEventListener('keydown', (e) => {
    if (e.key === ' ' || e.key === 'Enter'){
      e.preventDefault();
      if (!$('qrCard').classList.contains('hidden') && !state.flipped) flip();
    }
    if (state.flipped && ['1', '2', '3', '4'].includes(e.key)){
      grade(['done', 'almost', 'needs', 'again'][+e.key - 1]);
    }
  });
  reset();
  loadKaTeX();
});