# Template 9: Matching Game

## Purpose
Interactive term ↔ definition pairing: two shuffled columns, click-to-match with instant feedback, error counter and win state. Best for vocabulary (física: magnitudes, unidades), authors↔works, formulas↔names, symbols↔meaning.

## Canonical boilerplate (copy, don't rewrite)

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/matching.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/matching.js')` → paste into `<script>`. **Fill in ONLY** the `PAIRS` (and optional `PAIR_COLORS`) consts. Do not modify the engine functions.

HTML skeleton with the fixed element IDs the engine looks up:

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> — matching.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   ├── .sub — metadata line
│   │   └── .stats (✅ <span id="matchMoves">, ❌ <span id="matchErrors">)
│   ├── <div class="wrap">
│   │   ├── <div id="matchStatus" role="status" aria-live="polite">
│   │   ├── <div id="matchWrap" class="match-grid">
│   │   │   ├── <div class="col"><div class="col-title">Términos</div><div id="matchLeft"></div></div>
│   │   │   └── <div class="col"><div class="col-title">Definiciones</div><div id="matchRight"></div></div>
│   │   └── <div id="matchSummary" class="hidden">
│   ├── .bottom-bar (#matchReset button)
│   └── <script> — matching.js
```

## Data format

```javascript
const PAIRS = [
  { id:'p1', term:'<b>Masa</b>', def:'Cantidad de materia de un cuerpo' },
  { id:'p2', term:'<b>Peso</b>', def:'Fuerza que la gravedad ejerce sobre la masa' }
];
const PAIR_COLORS = {};   // optional: { p1:'#5b7fc4', ... } per-pair hint color
```

- Terms go on the left, definitions on the right. Both columns are shuffled independently by the engine — do NOT pre-shuffle.
- 6–14 pairs (more makes the grid unwieldy).
- Keep terms short (2–5 words); definitions can be 1–2 sentences. No duplicated text across pairs.
- Math in terms/definitions uses the `$$LaTeX$$ fallback-text` convention (see the Mathematics section in SKILL.md).

## Behavior notes (engine-enforced, do not override)

- Correct pairs lock in place (green + ✓). Wrong pairs flash red and count as errors.
- **A wrong attempt flashes ONLY the just-clicked card red; the selected card stays selected** so the user can immediately retry — the rest of the grid never moves or lights up.
- **Clicking the already-selected card deselects it** (toggle); clicking an opposite-column card attempts the match; clicking another card in the same column re-selects.
- Win state renders the summary card inside `#matchSummary` with a "Jugar de nuevo" button.
- Keyboard: every card is a `<button>` — Enter/Space selects and matches.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md
  - Select 6-14 high-value term/definition pairs from the wiki
  - Definitions must be precise enough to be unambiguous, but share vocabulary
    style so matching is not trivial (no unique keywords that only appear once)
  - Write ALL content yourself

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first
  - Set the `← theme` vars in the copied CSS

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/matching.css into <style>, set the theme vars
  - Copy assets/matching.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in PAIRS (and PAIR_COLORS if desired)

STEP 4 — SELF-CHECK (each item must pass)
  - Every pair has a unique id; 6-14 pairs total
  - No term equals any definition; no pair shares sentences with another pair
  - The PAIRS array parses as valid JSON when copied to a .json file
  - Left column terms are nouns/phrases; right column starts with verb phrases or sentences
  - Every formula follows `$$LaTeX$$ fallback-text` (never bare LaTeX without fallback)

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="match", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```
