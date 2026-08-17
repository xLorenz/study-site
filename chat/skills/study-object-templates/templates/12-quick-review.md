# Template 12: Quick Review (Concept Categorization)

## Purpose
A quick review deck where the student categorizes every concept with one of four fixed grades — **Logrado (green) → Casi (blue) → Necesita trabajo (yellow) → Otra vez (red)** — and ends with a per-category breakdown, a "Repasar los difíciles" second pass and a tagged list of the concepts to work on. Best for the last hours before an exam: broad coverage, honest triage, focused re-study.

## Canonical boilerplate (copy, don't rewrite)

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/quick-review.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/quick-review.js')` → paste into `<script>`. **Fill in ONLY** the `DECK` and `TOPIC_COLORS` consts. The four categories are FIXED in the engine (`CATEGORIES`) — do not rename them. Do not modify the engine functions.

HTML skeleton with the fixed element IDs the engine looks up:

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> — quick-review.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   ├── .sub — metadata line
│   │   └── .stats
│   │       ├── .stat.reviewed-stat (<span id="qrReviewed">)
│   │       ├── #qrCounts:
│   │       │   ├── .stat.stat-cat (.cat-dot style="background:#4ade80" + <span id="qrDone">)
│   │       │   ├── .stat.stat-cat (.cat-dot background:#60a5fa + <span id="qrAlmost">)
│   │       │   ├── .stat.stat-cat (.cat-dot background:#fbbf24 + <span id="qrNeeds">)
│   │       │   └── .stat.stat-cat (.cat-dot background:#f87171 + <span id="qrAgain">)
│   │       └── <span id="qrWeakBadge" class="stat hidden">Repaso de difíciles</span>
│   ├── <div class="wrap">
│   │   ├── <div id="qrCard" class="hidden">
│   │   │   ├── .card-inner
│   │   │   │   ├── .card-face.card-front > <div id="qrFront">
│   │   │   │   └── .card-face.card-back > <div id="qrBack"> + <div id="qrHint" class="hidden">
│   │   ├── .action-row
│   │   │   └── <button id="qrFlip">Mostrar respuesta</button>
│   │   ├── <div id="qrGrades" class="hidden">
│   │   │   ├── <button data-cat="done">1 · Logrado</button>
│   │   │   ├── <button data-cat="almost">2 · Casi</button>
│   │   │   ├── <button data-cat="needs">3 · Necesita trabajo</button>
│   │   │   └── <button data-cat="again">4 · Otra vez</button>
│   │   ├── <div id="qrSummary" class="hidden">
│   │   │   ├── <div id="qrSummaryBody">
│   │   │   └── .summary-actions
│   │   │       ├── <button id="qrWeakBtn" class="btn-primary">
│   │   │       ├── <button id="qrListBtn" class="btn-ghost">Ver lista</button>
│   │   │       └── <button id="qrResetBtn" class="btn-ghost">Reiniciar</button>
│   │   ├── <div id="qrListPanel" class="hidden">
│   │   │   ├── <h2>Conceptos por categoría</h2>
│   │   │   ├── <div id="qrList">
│   │   │   └── <button id="qrListClose">Cerrar lista</button>
│   │   └── .hint (keyboard shortcuts, <kbd> tags)
│   ├── .bottom-bar (#qrReset button)
│   └── <script> — quick-review.js
```

## Data format

```javascript
const DECK = [
  { id:'d1', topic:'cinematica', topicLabel:'Cinemática',
    front:'<b>¿Ecuación de posición en MRUV?</b>',
    back:'<p>$$x = x_0 + v_0 t + \\frac{1}{2} a t^2$$ x = x0 + v0·t + ½·a·t²</p>',
    hint:'<p>Empieza por x0 y v0·t...</p>' }
];
const TOPIC_COLORS = { cinematica:'#5b7fc4' };
```

- `front` is a question/prompt (HTML), `back` the answer (HTML). Math uses the `$$LaTeX$$ fallback-text` convention (see the Mathematics section in SKILL.md).
- `hint` optional: empty string = no hint. Hints nudge, they never answer.
- 15–40 cards per deck. `id` unique, every `topic` key present in `TOPIC_COLORS` (max 4 topics).

## Behavior notes (engine-enforced, do not override)

- Cards present once, shuffled. Flip (button, Space or Enter), then grade with 1–4.
- "Repasar los difíciles" runs a **round over ONLY the non-Logrado cards** (Otra vez → Necesita trabajo → Casi priority, shuffled within each group), behaving exactly like a normal run. When the round ends the summary appears again; any card still not Logrado stays in the pool and can be reviewed again with the same button. Rounds repeat until everything is Logrado.
- The list panel groups every concept by its category, each tagged with the category color and its topic badge; answers toggle inline.
- Keyboard: Space/Enter flips, 1–4 grades.
- Print: cards print expanded; the summary and list print as-is.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md
  - Select 15-40 recall units (formula + meaning, definition, constant...)
  - Front = prompt, back = answer; both self-contained (no "ver wiki")
  - Spread cards across the wiki's major topics (2-4 topics)
  - Write ALL content yourself

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first
  - Set the `← theme` vars in the copied CSS; pick TOPIC_COLORS hues from the theme

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/quick-review.css into <style>, set the theme vars
  - Copy assets/quick-review.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in DECK and TOPIC_COLORS

STEP 4 — SELF-CHECK (each item must pass)
  - Every id unique; every topic key has a TOPIC_COLORS entry
  - Every front is a question/prompt; every back answers it directly
  - The DECK array parses as valid JSON when copied to a .json file
  - Every formula follows `$$LaTeX$$ fallback-text` (never bare LaTeX without fallback)
  - No card answers another card's front verbatim

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="review", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```