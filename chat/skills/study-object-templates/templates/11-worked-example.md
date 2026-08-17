# Template 11: Worked-Example Walkthrough

## Purpose
Step-by-step solved problem with progressive reveal: the problem stays visible, steps unlock one at a time, each step can carry a hint, and the final answer card appears last. Best for math/physics problems, proofs, algorithm traces, code walkthroughs.

## Canonical boilerplate (copy, don't rewrite)

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/worked-example.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/worked-example.js')` → paste into `<script>`. **Fill in ONLY** the `EXAMPLE` const. Do not modify the engine functions.

HTML skeleton with the fixed element IDs the engine looks up:

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> — worked-example.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   └── .sub — metadata line
│   ├── <div class="wrap">
│   │   ├── .progress-row (.progress-track > <div id="stepProgress">, <span id="stepCount">)
│   │   ├── <section id="problemCard" class="problem-card">
│   │   │   ├── .card-label ("Problema")
│   │   │   └── <div id="problemBody">
│   │   ├── <div id="stepsList"></div>
│   │   ├── <section id="answerCard" class="answer-card hidden">
│   │   │   ├── .card-label ("Resultado")
│   │   │   └── <div id="answerBody">
│   │   └── .hint (keyboard shortcuts, <kbd> tags)
│   ├── .bottom-bar (#btnRestart, #btnNextStep, #btnRevealAll)
│   └── <script> — worked-example.js
```

## Data format

```javascript
const EXAMPLE = {
  problem: '<p>Un bloque de 2 kg desliza... Calcular la velocidad al llegar al suelo.</p>',
  steps: [
    { title:'Datos e incógnita',
      body:'<p>m = 2 kg, g = 9,8 m/s², h = 5 m...</p>',
      hint:'<p>¿Qué magnitudes se conservan?</p>' },
    { title:'Elegir método',
      body:'<p>Se conserva la energía mecánica...</p>',
      hint:'' }
  ],
  answer: '<p>v = 9,9 m/s</p>'
};
```

- 3–7 steps is the sweet spot. Steps must be ordered and self-contained (each builds on the previous).
- `body` is HTML — math uses the `$$LaTeX$$ fallback-text` convention (see the Mathematics section in SKILL.md); `$$...$$` renders with KaTeX when online, the plain fallback text when offline.
- `hint` is optional: empty string = no hint button for that step. Hints hint, they never give the answer.
- `problem` and `answer` are HTML strings.

## Behavior notes (engine-enforced, do not override)

- **Steps are built once at load; revealing a step only animates THAT step** — the already-revealed steps never re-animate.
- Steps unlock strictly in order; locked steps are visibly dimmed. Revealed steps stay visible (progressive buildup).
- Each revealed step shows its "Pista" button only when the step has a hint. Step headers are `<div>`s (not buttons).
- The answer card appears only after the last step is revealed.
- Keyboard: `N` reveals next step, `H` toggles the hint of the last revealed step.
- Print: all steps and the answer print fully expanded.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md
  - Pick ONE representative problem per object (a walkthrough is deep, not broad)
  - Decompose the solution into 3-7 ordered steps; each step = ONE operation
    or reasoning unit, with a clear title
  - Every step body explains the WHY, not just the next operation
  - Include the numeric/symbolic result in the final answer card

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first
  - Set the `← theme` vars in the copied CSS

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/worked-example.css into <style>, set the theme vars
  - Copy assets/worked-example.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in the EXAMPLE const

STEP 4 — SELF-CHECK (each item must pass)
  - The problem is solvable from the wiki content; steps cover the whole path
  - Steps are ordered, each body is HTML with no unescaped quotes; EXAMPLE parses as valid JSON
  - At least one step has a hint; hints never reveal the final result
  - Answer card states the final result clearly with units/significance
  - Every formula follows `$$LaTeX$$ fallback-text` (never bare LaTeX without fallback)

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="steps", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```
