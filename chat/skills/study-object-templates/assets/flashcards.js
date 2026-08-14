/**
 * flashcards.js — canonical interactive flashcards engine.
 * Copy this file verbatim into <script> in the generated HTML.
 * Fill in ONLY the three const declarations at the top: QUESTIONS, TOPIC_COLORS, DIFF_COLORS.
 * Do not modify any function below — they are production-tested.
 */

const QUESTIONS = [
  /* Fill me. Every entry:
     { id:'q1', tag:'topic-key', tagLabel:'Display', diff:'Media',
       question:'...', options:['A','B','C','D'], correct:0,
       explanation:'why correct + why each distractor is wrong',
       detail:'extra expansion with examples' }
     See references/flashcard-design.md for the full quality rules.
     REQUIRED: unique id, exactly 4 options, correct in [0..3], diff present. */
];

/* Keys must match every q.tag. Pull hues from the subject theme. */
const TOPIC_COLORS = {};

/* Difficulty labels and their colors — adjust to the labels you use
   (suggested: 'Baja', 'Media', 'Alta'; more granular: 'Media-Alta', 'Niche'). */
const DIFF_COLORS = { 'Baja':'#4ade80', 'Media':'#fbbf24', 'Alta':'#fb923c' };

const LETTERS = ['A','B','C','D'];

function shuffle(arr){
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--){
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const state = {
  cards: [], order: [], current: 0,
  answers: {}, correctCount: 0, wrongCount: 0, answeredCount: 0
};

function initGame(){
  state.cards = QUESTIONS.map(q => {
    const opts = shuffle(q.options);                 // options shuffled per question
    const correct = opts.indexOf(q.options[q.correct]);
    return Object.assign({}, q, { options: opts, correct: correct, color: TOPIC_COLORS[q.tag] });
  });
  state.order = state.cards.map((_, i) => i);        // fixed order: difficulty ascending
  state.current = 0;
  state.answers = {};
  state.correctCount = 0;
  state.wrongCount = 0;
  state.answeredCount = 0;
  document.getElementById('btnReset').style.display = 'none';
  render();
}

function updateStats(){
  document.getElementById('statOk').textContent = state.correctCount;
  document.getElementById('statBad').textContent = state.wrongCount;
  document.getElementById('statTotal').textContent = state.answeredCount + '/' + state.cards.length;
  document.getElementById('progressFill').style.width = (state.answeredCount / state.cards.length * 100) + '%';
}

function render(){
  if (state.current >= state.cards.length){ renderResults(); return; }
  const idx = state.order[state.current];
  const card = state.cards[idx];
  const answered = (idx in state.answers);
  const chosen = answered ? state.answers[idx] : null;

  updateStats();
  document.getElementById('counter').textContent = (state.current + 1) + ' / ' + state.cards.length;

  let html = '<div class="card"><div class="card-top">'
    + '<span class="badge" style="--c:' + card.color + '">' + card.tagLabel + '</span>'
    + '<span class="badge" style="--c:' + DIFF_COLORS[card.diff] + '">' + card.diff + '</span>'
    + '</div><div class="q-num">Ejercicio ' + (state.current + 1) + ' · ' + card.diff + '</div>'
    + '<h2 class="question">' + card.question + '</h2><div class="options">';

  card.options.forEach((opt, oi) => {
    let cls = 'option';
    if (answered){
      if (oi === card.correct) cls += ' correct';
      else if (oi === chosen) cls += ' wrong';
      else cls += ' dim';
    }
    html += '<button class="' + cls + '" data-oi="' + oi + '"' + (answered ? ' disabled' : '') + '>'
      + '<span class="letter">' + LETTERS[oi] + '</span><span class="opt-text">' + opt + '</span></button>';
  });
  html += '</div>';

  if (answered){
    const ok = (chosen === card.correct);
    html += '<div class="feedback ' + (ok ? 'ok' : 'bad') + '" role="status" aria-live="polite">'
      + '<div class="fb-head">' + (ok ? '✓ Correcto' : '✗ Incorrecto') + '</div>'
      + '<div class="fb-correct">Respuesta correcta: <strong>' + LETTERS[card.correct] + ') ' + card.options[card.correct] + '</strong></div>'
      + '<div class="fb-explain"><span class="fb-label">Explicación</span>' + card.explanation + '</div>'
      + '<div class="fb-detail"><span class="fb-label">Resolución</span>' + card.detail + '</div>'
      + '</div>';
  }
  html += '</div>';
  document.getElementById('cardArea').innerHTML = html;

  if (!answered){
    document.querySelectorAll('.option').forEach(btn => {
      btn.addEventListener('click', () => handleAnswer(idx, parseInt(btn.dataset.oi, 10)));
    });
    const first = document.querySelector('.option');
    if (first) first.focus();
  }

  document.getElementById('btnPrev').disabled = (state.current === 0);
  /* Sequential navigation with no skipping: Next is DISABLED while the current
     card is unanswered, and always advances to the literal next card.
     Reaching the end only finishes once every card has been answered. */
  const currentAnswered = (idx in state.answers);
  const finished = (state.current + 1 >= state.cards.length && state.answeredCount === state.cards.length);
  document.getElementById('btnNext').disabled = !currentAnswered;
  document.getElementById('btnNext').textContent = finished ? 'Ver resultados' : 'Siguiente →';
  document.getElementById('btnReset').style.display = 'none';
}

function handleAnswer(cardIdx, chosen){
  const card = state.cards[cardIdx];
  state.answers[cardIdx] = chosen;
  state.answeredCount++;
  if (chosen === card.correct){ state.correctCount++; confettiBurst(); }
  else { state.wrongCount++; }
  render();
}

function nextCard(){
  /* Guard: never advance past an unanswered card (button + keyboard) */
  const idx = state.order[state.current];
  if (!(idx in state.answers)) return;
  if (state.current + 1 < state.cards.length){ state.current++; render(); }
  else if (state.answeredCount === state.cards.length){ state.current = state.cards.length; render(); }
}

function prevCard(){
  if (state.current > 0){ state.current--; render(); }
}

function renderResults(){
  const total = state.cards.length;
  const pct = Math.round(state.correctCount / total * 100);
  const msg = pct >= 90 ? 'Excelente dominio de la materia.'
    : pct >= 70 ? 'Muy buen nivel; revisá los ejercicios marcados en rojo.'
    : pct >= 50 ? 'Aprobado, pero conviene repasar los conceptos fallados.'
    : 'Es recomendable repasar el material de la wiki antes de rendir.';

  const topics = {};
  state.cards.forEach((card, i) => {
    if (!topics[card.tag]) topics[card.tag] = { name: card.tagLabel, color: card.color, total: 0, ok: 0 };
    topics[card.tag].total++;
    if (state.answers[i] === card.correct) topics[card.tag].ok++;
  });

  let topicsHtml = '';
  Object.keys(topics).forEach(k => {
    const t = topics[k];
    topicsHtml += '<div class="topic-row"><span class="dot" style="background:' + t.color + '"></span>'
      + '<span class="tname">' + t.name + '</span>'
      + '<span class="tval">' + t.ok + '/' + t.total + '</span></div>';
  });

  document.getElementById('cardArea').innerHTML =
    '<div class="card results-card">'
    + '<div class="score-circle" style="--pct:' + pct + '"><span class="num">' + pct + '%</span><span class="lbl">aciertos</span></div>'
    + '<h2>Resultado</h2>'
    + '<div class="msg">' + msg + '</div>'
    + '<div class="msg" style="margin-bottom:18px">✅ ' + state.correctCount + ' correctas · ❌ ' + state.wrongCount + ' incorrectas · 📊 ' + total + ' ejercicios</div>'
    + '<div class="topics">' + topicsHtml + '</div>'
    + '<div class="results-actions"><button onclick="initGame()">↺ Reintentar (barajar de nuevo)</button></div>'
    + '</div>';

  updateStats();
  document.getElementById('counter').textContent = 'Resultados';
  document.getElementById('btnPrev').disabled = false;
  document.getElementById('btnNext').style.display = 'none';
  document.getElementById('btnReset').style.display = 'inline-block';
}

/* Confetti */
const canvas = document.getElementById('confetti');
const ctx = canvas.getContext('2d');
let particles = [];
function confettiBurst(){
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const colors = ['#4db0b0','#6ec4c4','#fbbf24','#4fc1ff','#f472b6','#4ade80'];
  for (let i = 0; i < 120; i++){
    particles.push({
      x: canvas.width / 2, y: canvas.height * 0.35,
      vx: (Math.random() - 0.5) * 15, vy: (Math.random() - 0.5) * 15 - 4,
      c: colors[i % colors.length], s: Math.random() * 5 + 3, life: 1
    });
  }
  requestAnimationFrame(drawConfetti);
}
function drawConfetti(){
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  particles.forEach(p => {
    p.x += p.vx; p.y += p.vy; p.vy += 0.28; p.life -= 0.012;
    ctx.globalAlpha = Math.max(0, p.life);
    ctx.fillStyle = p.c;
    ctx.fillRect(p.x, p.y, p.s, p.s);
  });
  particles = particles.filter(p => p.life > 0 && p.y < canvas.height + 60);
  ctx.globalAlpha = 1;
  if (particles.length) requestAnimationFrame(drawConfetti);
  else ctx.clearRect(0, 0, canvas.width, canvas.height);
}

/* Events */
document.getElementById('btnNext').addEventListener('click', nextCard);
document.getElementById('btnPrev').addEventListener('click', prevCard);
document.getElementById('btnReset').addEventListener('click', () => { document.getElementById('btnNext').style.display = ''; initGame(); });
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight') nextCard();
  else if (e.key === 'ArrowLeft') prevCard();
  else if (['1','2','3','4'].includes(e.key) && state.current < state.cards.length){
    const idx = state.order[state.current];
    if (!(idx in state.answers)){
      const oi = parseInt(e.key, 10) - 1;
      if (oi < state.cards[idx].options.length) handleAnswer(idx, oi);
    }
  }
});

initGame();