# Template 14: Comparison Matrix

## Purpose
Concepts side by side across shared dimensions: rows = comparison dimensions, columns = concepts, with sticky headers, column focus, search and expandable long cells. Best for classic contrasts (meiosis vs mitosis, TCP vs UDP, choque elástico vs inelástico, MRU vs MRUV).

## Canonical boilerplate (copy, don't rewrite)

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/comparison.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/comparison.js')` → paste into `<script>`. **Fill in ONLY** the `CONCEPTS` and `DIMENSIONS` consts. Do not modify the engine functions.

HTML skeleton with the fixed element IDs the engine looks up:

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> — comparison.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   └── .sub — metadata line
│   ├── <div class="wrap">
│   │   ├── .controls
│   │   │   ├── .control-row (#cmpSearch input + #cmpReset button)
│   │   │   └── #cmpFocusBar (focus chips, filled by engine)
│   │   ├── .cmp-count (<span id="cmpCount">)
│   │   ├── .table-wrap
│   │   │   └── <table id="cmpTable">
│   │   │       ├── <thead id="cmpTHead">
│   │   │       └── <tbody id="cmpTBody">
│   └── <script> — comparison.js
```

## Data format

```javascript
const CONCEPTS = [
  { key:'mru',  label:'MRU',  color:'#5b7fc4' },
  { key:'mruv', label:'MRUV', color:'#fbbf24' }
];

const DIMENSIONS = [
  { id:'d1', label:'Aceleración',
    cells: {
      mru:  '<p>a = 0</p>',
      mruv: '<p>a = constante ≠ 0</p>'
    } },
  { id:'d2', label:'Ecuación de posición',
    cells: {
      mru:  '<p class="muted">x = x₀ + v·t</p>',
      mruv: '<p>x = x₀ + v₀·t + ½·a·t²</p>'
    } }
];
```

- 2–4 concepts (columns), 6–12 dimensions (rows). Every concept needs a cell for EVERY dimension — use `-`/`No aplica` when there is nothing to say.
- Cells are HTML strings; math uses the `$$LaTeX$$ fallback-text` convention (see the Mathematics section in SKILL.md) — e.g. `$$v = v_0 + a t$$ v = v₀ + a·t`; use `<p class="muted">` for secondary info.
- `color` per concept drives the column header; `id` per dimension is required.

## Behavior notes (engine-enforced, do not override)

- First column (dimension label) is sticky; column headers are sticky on vertical scroll.
- Long cells clamp to two lines with an "Expandir/Contraer" toggle (toggle state resets on re-render).
- Focus chips pin one column (dims the rest); hovering a column dims the others temporarily.
- Search filters rows by dimension label OR cell text.
- Print: full matrix, all cells expanded, no dimming.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md
  - Pick 2-4 concepts that genuinely contrast (from the wiki)
  - Define 6-12 dimensions that expose the DIFFERENCES (and shared ground)
  - Fill every cell from the wiki; keep cells 1-3 sentences; no empty cells
  - Write ALL content yourself

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first
  - Set the `← theme` vars in the copied CSS; pick concept colors from the theme

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/comparison.css into <style>, set the theme vars
  - Copy assets/comparison.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in CONCEPTS and DIMENSIONS

STEP 4 — SELF-CHECK (each item must pass)
  - Every dimension has a cell for every concept (no missing keys)
  - Dimensions are consistent: the same aspect is compared in each row
  - Cells differ meaningfully between concepts (a matrix where everything
    says the same thing is useless)
  - The consts parse as valid JSON when copied to a .json file
  - Every formula follows `$$LaTeX$$ fallback-text` (never bare LaTeX without fallback)

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="compare", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```
