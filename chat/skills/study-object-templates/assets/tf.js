/**
 * tf.js - canonical True/False rapid round engine.
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the STATEMENTS, TOPIC_COLORS and DEFAULT_SECONDS consts.
 * Do not modify the functions below - they are the canonical implementation.
 *
 * Data model (see templates/13-true-false.md):
 *   STATEMENTS: [{ id:'t1', topic:'cinematica', topicLabel:'Cinematica',
 *                  statement:'<b>En el MRU la aceleracion es nula.</b>',
 *                  answer:true, diff:1, explanation:'<p>...</p>' }]
 *     diff: 1 = facil, 2 = media, 3 = dificil. Defaults to 1 when missing.
 *     The round ALWAYS runs easy -> medium -> hard, shuffled within each
 *     difficulty, so questions get harder as the round progresses.
 *   TOPIC_COLORS: { cinematica:'#5b7fc4', ... }
 *   DEFAULT_SECONDS: seconds per statement when the student picks "Normal".
 *
 * Rules enforced here:
 *   - The round does NOT start on load: an intro screen offers a difficulty
 *     picker (Relajado / Normal / Reto / Experto -> seconds per question).
 *   - One statement at a time with a shrinking timer bar. Timeout counts as
 *     a wrong answer and reveals the correct one. Answering FREEZES the bar
 *     where it is (no ghost-counting) and the remaining seconds keep their
 *     last value. Under 6 seconds left the count and the bar turn red and
 *     pulse.
 *   - Answering shows immediate feedback + explanation; "Siguiente" advances.
 *   - Keyboard: T = True, F = False, Enter = next.
 *   - Results screen: score circle, elapsed total time, per-topic accuracy
 *     bars and a "Para repasar" list of the statements answered wrong or
 *     timed out, each tagged with its topic color. Restart with the same
 *     difficulty or go back to the picker.
 *
 * Required HTML (see templates/13-true-false.md):
 *   #tfIntro (#tfDiffButtons with data-sec buttons, #tfStartInfo),
 *   #tfCard, #tfStatement, #tfTrue, #tfFalse,
 *   #tfTimerBar, #tfTimerText, #tfFeedback, #tfNext,
 *   #tfScore, #tfProgress, #tfRestart, #tfResults, #tfSummary,
 *   #tfTimeTotal, #tfMissedList
 */

const STATEMENTS = [
  /* Fill me. { id:'t1', topic:'...', topicLabel:'...', statement:'...', answer:true, diff:1, explanation:'...' } */
];

/* Keys must match every s.topic. Pull hues from the subject theme. */
const TOPIC_COLORS = {};

/* Seconds per statement used when the student picks "Normal". */
const DEFAULT_SECONDS = 20;

/* Fixed difficulty picker options: label -> seconds. Do not remove keys. */
const DIFFICULTIES = [
  { key: 'relaxed',  label: 'Relajado',  sub: '30 s por pregunta', sec: 30 },
  { key: 'normal',   label: 'Normal',    sub: DEFAULT_SECONDS + ' s por pregunta', sec: DEFAULT_SECONDS },
  { key: 'challenge',label: 'Reto',      sub: '10 s por pregunta', sec: 10 },
  { key: 'expert',   label: 'Experto',   sub: '6 s por pregunta',  sec: 6 }
];

/* ---- state ---- */
const state = { order: [], current: 0, score: 0, wrong: 0, timeout: false, answered: false, topicStats: {}, missed: [], sec: DEFAULT_SECONDS, startTime: 0 };

const $ = (id) => document.getElementById(id);

function shuffle(arr){
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--){
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function buildOrder(){
  const groups = { 1: [], 2: [], 3: [] };
  STATEMENTS.forEach((s, i) => {
    groups[s.diff || 1].push(i);
  });
  return [].concat(shuffle(groups[1]), shuffle(groups[2]), shuffle(groups[3]));
}

let timer = null, elapsed = 0, lowWarned = false;

function setTimerLow(low){
  $('tfTimerText').classList.toggle('low', low);
  $('tfTimerBar').classList.toggle('low', low);
}

function startTimer(){
  clearInterval(timer);
  elapsed = 0;
  lowWarned = false;
  setTimerLow(false);
  $('tfTimerBar').style.transition = 'none';
  $('tfTimerBar').style.width = '100%';
  requestAnimationFrame(() => {
    $('tfTimerBar').style.transition = 'width ' + state.sec + 's linear';
    $('tfTimerBar').style.width = '0%';
  });
  $('tfTimerText').textContent = state.sec.toFixed(1) + 's';
  timer = setInterval(() => {
    elapsed += 0.1;
    const left = Math.max(0, state.sec - elapsed);
    $('tfTimerText').textContent = left.toFixed(1) + 's';
    if (left <= 5 && !lowWarned){
      lowWarned = true;
      setTimerLow(true);
    }
    if (elapsed >= state.sec){
      clearInterval(timer);
      if (!state.answered) answer(null);
    }
  }, 100);
}

function stopTimerVisuals(){
  clearInterval(timer);
  const left = Math.max(0, state.sec - elapsed);
  const pct = (left / state.sec) * 100;
  $('tfTimerBar').style.transition = 'none';
  $('tfTimerBar').style.width = pct + '%';
  $('tfTimerText').textContent = left.toFixed(1) + 's';
}

function renderCard(){
  const s = STATEMENTS[state.order[state.current]];
  $('tfStatement').innerHTML =
    '<span class="badge" style="--c:' + (TOPIC_COLORS[s.topic] || '#5b7fc4') + '">' + s.topicLabel + '</span>' +
    '<span class="badge diff-badge">Dificultad ' + (s.diff || 1) + '/3</span>' +
    '<div class="tf-statement-text">' + s.statement + '</div>';
  $('tfScore').textContent = state.score;
  $('tfProgress').textContent = (state.current + 1) + ' / ' + STATEMENTS.length;
  $('tfFeedback').className = 'tf-feedback hidden';
  $('tfTrue').disabled = false;
  $('tfFalse').disabled = false;
  $('tfTrue').classList.remove('wrong-pick', 'answered');
  $('tfFalse').classList.remove('wrong-pick', 'answered');
  $('tfNext').classList.add('hidden');
  state.answered = false;
  state.timeout = false;
  renderMath();
  startTimer();
}

function answer(pick){
  if (state.answered) return;
  state.answered = true;
  stopTimerVisuals();
  const s = STATEMENTS[state.order[state.current]];
  const correct = pick === s.answer;
  if (correct) state.score++;
  else state.wrong++;
  if (!correct) state.missed.push(state.order[state.current]);
  state.topicStats[s.topic] = state.topicStats[s.topic] || { ok: 0, total: 0 };
  state.topicStats[s.topic].total++;
  if (correct) state.topicStats[s.topic].ok++;

  const fb = $('tfFeedback');
  fb.classList.remove('hidden');
  fb.classList.add(correct ? 'ok' : 'bad');
  fb.innerHTML =
    '<div class="fb-head">' + (correct ? 'Correcto' : (state.timeout ? 'Tiempo agotado' : 'Incorrecto')) + '</div>' +
    '<div class="fb-correct">Respuesta correcta: <strong>' + (s.answer ? 'Verdadero' : 'Falso') + '</strong></div>' +
    '<div class="fb-explain">' + (s.explanation || '') + '</div>';
  renderMath();
  $('tfTrue').disabled = true;
  $('tfFalse').disabled = true;
  const correctBtn = s.answer ? $('tfTrue') : $('tfFalse');
  correctBtn.classList.add('answered');
  if (!correct) (pick === true ? $('tfTrue') : $('tfFalse')).classList.add('wrong-pick');
  $('tfNext').classList.remove('hidden');
  $('tfScore').textContent = state.score;
}

function next(){
  state.current++;
  if (state.current >= STATEMENTS.length) finish();
  else renderCard();
}

function fmtTime(ms){
  const s = Math.round(ms / 1000);
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
}

function finish(){
  clearInterval(timer);
  const totalMs = Date.now() - state.startTime;
  $('tfCard').classList.add('hidden');
  $('tfResults').classList.remove('hidden');
  const total = STATEMENTS.length;
  const pct = Math.round((state.score / total) * 100);
  $('tfSummary').innerHTML =
    '<h2>Ronda finalizada</h2>' +
    '<div class="score-circle" style="--pct:' + pct + '">' +
      '<span class="num">' + state.score + '/' + total + '</span>' +
      '<span class="lbl">aciertos</span>' +
    '</div>' +
    '<p class="msg">Precisión: ' + pct + '% · Tiempo total: <span id="tfTimeTotal">' + fmtTime(totalMs) + '</span></p>' +
    '<div class="topics">' + Object.keys(state.topicStats).map(t => {
      const st = state.topicStats[t];
      return '<div class="topic-row">' +
        '<span class="dot" style="background:' + (TOPIC_COLORS[t] || '#5b7fc4') + '"></span>' +
        '<span class="tname">' + t + '</span>' +
        '<span class="tval">' + st.ok + '/' + st.total + '</span></div>';
    }).join('') + '</div>';
  const missedEl = $('tfMissedList');
  if (state.missed.length){
    missedEl.classList.remove('hidden');
    missedEl.innerHTML =
      '<h3>Para repasar</h3>' +
      '<div class="missed-items">' + state.missed.map(i => {
        const s = STATEMENTS[i];
        return '<div class="missed-item">' +
          '<span class="badge" style="--c:' + (TOPIC_COLORS[s.topic] || '#5b7fc4') + '">' + s.topicLabel + '</span>' +
          '<span class="missed-text">' + s.statement + '</span>' +
          '<span class="missed-ans">' + (s.answer ? 'Verdadero' : 'Falso') + '</span>' +
        '</div>';
      }).join('') + '</div>';
  } else {
    missedEl.classList.add('hidden');
  }
  $('tfResults').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function startRound(sec){
  state.sec = sec;
  state.order = buildOrder();
  state.current = 0;
  state.score = 0;
  state.wrong = 0;
  state.topicStats = {};
  state.missed = [];
  state.startTime = Date.now();
  $('tfIntro').classList.add('hidden');
  $('tfCard').classList.remove('hidden');
  $('tfResults').classList.add('hidden');
  renderCard();
}

function backToIntro(){
  clearInterval(timer);
  $('tfCard').classList.add('hidden');
  $('tfResults').classList.add('hidden');
  $('tfIntro').classList.remove('hidden');
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
  const diffBar = $('tfDiffButtons');
  DIFFICULTIES.forEach(d => {
    const b = document.createElement('button');
    b.className = 'diff-btn';
    b.dataset.sec = d.sec;
    b.innerHTML = '<span class="diff-name">' + d.label + '</span><span class="diff-sub">' + d.sub + '</span>';
    b.addEventListener('click', () => startRound(d.sec));
    diffBar.appendChild(b);
  });
  $('tfTrue').addEventListener('click', () => answer(true));
  $('tfFalse').addEventListener('click', () => answer(false));
  $('tfNext').addEventListener('click', next);
  $('tfRestart').addEventListener('click', () => startRound(state.sec));
  $('tfChangeDiff').addEventListener('click', backToIntro);
  document.addEventListener('keydown', (e) => {
    if (!$('tfIntro').classList.contains('hidden') && ['1', '2', '3', '4'].includes(e.key)){
      const d = DIFFICULTIES[+e.key - 1];
      if (d) startRound(d.sec);
    }
    if (e.key === 'ArrowLeft'){ e.preventDefault(); if (!$('tfCard').classList.contains('hidden')) answer(true); }
    if (e.key === 'ArrowRight'){ e.preventDefault(); if (!$('tfCard').classList.contains('hidden')) answer(false); }
    if ((e.key === 't' || e.key === 'T') && !$('tfCard').classList.contains('hidden')) answer(true);
    if ((e.key === 'f' || e.key === 'F') && !$('tfCard').classList.contains('hidden')) answer(false);
    if (e.key === 'Enter' && !$('tfNext').classList.contains('hidden')) next();
  });
  document.querySelectorAll('.hint').forEach(h => h.classList.add('hidden'));
  if (!document.querySelector('.tf-keys-hint')){
    const hint = document.createElement('p');
    hint.className = 'tf-keys-hint';
    hint.innerHTML = 'Atajos de teclado: ← Verdadero · Falso →';
    $('tfCard').appendChild(hint);
  }
  loadKaTeX();
});