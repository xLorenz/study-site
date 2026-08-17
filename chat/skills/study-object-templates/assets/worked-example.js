/**
 * worked-example.js - canonical worked-example walkthrough engine.
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the EXAMPLE const at the top.
 * Do not modify the functions below - they are the canonical implementation.
 *
 * Data model (see templates/11-worked-example.md):
 *   EXAMPLE = {
 *     problem: '<p>HTML problem statement...></p>',
 *     steps: [
 *       { title:'Identificar datos', body:'<p>HTML explanation...</p>',
 *         hint:'<p>Optional hint, HTML. Empty string = no hint.</p>' },
 *       ...
 *     ],
 *     answer: '<p>HTML final answer statement.</p>'
 *   }
 *
 * Rules enforced here:
 *   - The step list is BUILT ONCE at startup. Revealing a step only unlocks
 *     that single step (class toggle) - the other steps keep their DOM and
 *     never re-render or re-animate. Only the newly revealed step animates.
 *   - The problem card is always visible; revealed steps stay visible
 *     (progressive buildup). Each revealed step has a hint toggle ("Pista").
 *   - The final answer card appears only after the last step is revealed.
 *   - "Revelar todos" unlocks every remaining step at once; "Reiniciar"
 *     relocks everything. Progress is "Paso X de N" + a progress bar.
 *   - Keyboard: N reveals the next step, H toggles the hint of the last
 *     revealed step.
 *   - Print: steps print fully expanded (CSS override), hints hidden.
 *
 * Required HTML (see templates/11-worked-example.md):
 *   #problemCard, #stepsList, #answerCard,
 *   #btnNextStep, #btnRevealAll, #btnRestart,
 *   #stepCount, #stepProgress
 */

const EXAMPLE = {
  problem: '<p>...</p>',
  steps: [
    { title: 'Paso 1', body: '<p>...</p>', hint: '' },
    { title: 'Paso 2', body: '<p>...</p>', hint: '<p>...</p>' }
  ],
  answer: '<p>...</p>'
};

/* ---- state ---- */
const state = { revealed: 0 };

const $ = (id) => document.getElementById(id);

function stepEl(i){
  return $('stepsList').querySelectorAll('.we-step')[i];
}

function buildSteps(){
  const list = $('stepsList');
  list.innerHTML = '';
  EXAMPLE.steps.forEach((s, i) => {
    const art = document.createElement('article');
    art.className = 'we-step locked';
    art.innerHTML =
      '<div class="we-step-head">' +
        '<span class="we-step-num">' + (i + 1) + '</span>' +
        '<span class="we-step-title">' + s.title + '</span>' +
        '<span class="we-step-state">Bloqueado</span>' +
      '</div>' +
      '<div class="we-step-body">' + s.body +
        (s.hint
          ? '<button class="we-hint-btn" data-hint="' + i + '">Pista</button>' +
            '<div class="we-hint" data-hint-body="' + i + '" hidden>' + s.hint + '</div>'
          : '') +
      '</div>';
    list.appendChild(art);
    if (s.hint){
      const btn = art.querySelector('.we-hint-btn');
      btn.addEventListener('click', () => {
        const body = art.querySelector('[data-hint-body]');
        const open = body.hidden;
        body.hidden = !open;
        btn.classList.toggle('on', open);
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    }
  });
}

function setStepState(i, open){
  const art = stepEl(i);
  if (!art) return;
  art.classList.toggle('open', open);
  art.classList.toggle('locked', !open);
  art.querySelector('.we-step-state').textContent = open ? 'Resuelto' : 'Bloqueado';
}

function renderChrome(){
  const total = EXAMPLE.steps.length;
  $('stepCount').textContent = state.revealed + ' de ' + total;
  $('stepProgress').style.width = (state.revealed / total) * 100 + '%';
  $('btnNextStep').disabled = state.revealed >= total;
  $('btnNextStep').textContent = state.revealed >= total ? 'Completado' : 'Revelar paso ' + (state.revealed + 1);
  const ans = $('answerCard');
  ans.classList.toggle('hidden', state.revealed < total);
  if (state.revealed >= total){
    ans.querySelector('#answerBody').innerHTML = EXAMPLE.answer;
    renderMath();
  }
}

function nextStep(){
  if (state.revealed < EXAMPLE.steps.length){
    setStepState(state.revealed, true);
    state.revealed++;
    renderChrome();
    const last = stepEl(state.revealed - 1);
    if (last) last.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function revealAll(){
  while (state.revealed < EXAMPLE.steps.length){
    setStepState(state.revealed, true);
    state.revealed++;
  }
  renderChrome();
}

function restart(){
  for (let i = 0; i < EXAMPLE.steps.length; i++) setStepState(i, false);
  state.revealed = 0;
  renderChrome();
  $('problemCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
  $('problemCard').querySelector('#problemBody').innerHTML = EXAMPLE.problem;
  buildSteps();
  renderChrome();
  renderMath();
  $('btnNextStep').addEventListener('click', nextStep);
  $('btnRevealAll').addEventListener('click', revealAll);
  $('btnRestart').addEventListener('click', restart);
  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea') return;
    if (e.key === 'n' || e.key === 'N') nextStep();
    if (e.key === 'h' || e.key === 'H'){
      const openSteps = document.querySelectorAll('#stepsList .we-step.open');
      if (openSteps.length){
        const btn = openSteps[openSteps.length - 1].querySelector('.we-hint-btn');
        if (btn) btn.click();
      }
    }
  });
  loadKaTeX();
});