# Template 5: Interactive Cheat Sheet

## Purpose
A scannable, **interactive** reference sheet: compact cards, one concept per card, color-coded by topic, with category filters, a formulas-only toggle and a search bar. Cards expand independently in a **cascade** — opening a card only pushes the cards directly below it in its column, everything else stays put. Built for rapid lookup during study.

## Canonical boilerplate (copy, don't rewrite)

The JS engine and CSS are canonical files — **copy them verbatim** into the generated HTML:

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/cheat-sheet.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/cheat-sheet.js')` → paste into `<script>`. **Fill in ONLY** the `CARDS` and `TOPIC_COLORS` consts at the top. Do not modify the engine functions.

The engine expects these element IDs — keep them exact: `catFilters`, `formulaToggle`, `cheatSearch`, `clearSearch`, `resultCount`, `cardGrid`.

## HTML skeleton

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono)
│   ├── <style> — cheat-sheet.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <div class="wrap">
│   │   ├── <header> — <h1> + .sub (what the sheet covers)
│   │   ├── <div class="toolbar">
│   │   │   ├── <div id="catFilters">  ← rendered by the engine
│   │   │   ├── <label class="formula-toggle"><input type="checkbox" id="formulaToggle"> Solo fórmulas</label>
│   │   │   ├── <div class="search-wrap">
│   │   │   │   ├── <input id="cheatSearch" placeholder="Buscar…">
│   │   │   │   └── <span class="clear" id="clearSearch">✕
│   │   │   ├── <span id="resultCount">
│   │   │   └── </div>
│   │   ├── <div class="grid" id="cardGrid">  ← rendered by the engine
│   │   └── </div>
│   └── <script> — cheat-sheet.js
```

## Data format

```javascript
const CARDS = [
  {
    id: 'c1',
    cat: 'topic-key',          // theme/category key (color comes from TOPIC_COLORS)
    catLabel: 'Topic',
    kind: 'concept',           // 'concept' or 'formula'
    title: 'Concept name',
    summary: '1-2 sentence explanation',
    formula: '$$F = q(E + v \\times B)$$  F = q(E + v×B)',  // REQUIRED if kind==='formula'
    detail: '<p>Explanation, caveats, when to use…</p>'
  },
  ...
];
```

```javascript
const TOPIC_COLORS = {
  'topic-key': '#a78bfa',      // one entry per .cat used in CARDS; hues from the theme
};
```

## Card content rules (also in references/cheat-sheet-selection.md)

- **One concept per card**, title + 1-2 sentence summary. Short and concise.
- **Theorems, formulas, equations and constants** get `kind: 'formula'` (with the `formula` field). They belong to their topic **and** to the cross-topic formulas category — the toggle surfaces them regardless of the selected topic.
- `detail` carries the expansion content: explanation, validity conditions, common mistakes, when to use it.
- Formulas: write them **inside `$$…$$`** (LaTeX for KaTeX) **and** repeat them in plain unicode **after** the delimiters: `'$$F = q(E + v \\times B)$$  F = q(E + v×B)'`. KaTeX is loaded from **three CDNs in order** (jsdelivr → unpkg → cdnjs); if every CDN fails, the engine **removes the `$$…$$` blocks entirely** and shows the unicode — raw `\frac` etc. must never be visible. Always include unicode: `μ₀`, `×`, `∮`, `∫`, `√`, superscripts/subscripts.
- 15–30 cards for a full sheet; 2–3 per topic minimum.

## Engine layout & interaction (do not restyle)
- The engine splits cards into **FIXED columns** (`--cols` custom property + `.cc-col` column divs, `grid-template-columns: repeat(var(--cols, 3), 1fr)`), assigned in **reading order** (row-major: card i → column i % numCols). Column count depends only on container width — it never changes when a card opens, and columns are **never rebalanced**: opening a card only pushes the cards below it in its own column (cascade), the rest of the sheet stays put. Do NOT switch `#cardGrid` back to CSS `columns` (the browser rebalances and cards jump around).
- A closed card is **compact**: only the clickable `.cc-header` (badges + title + `+` hint) is visible, sized by content (`min-height: 96px`, no fixed tall height — no empty gap under the title). The `.cc-body` is hidden via `max-height:0; opacity:0`.
- Clicking the **header** toggles `.open`: the body expands **in flow** (the card's column grows; `position:absolute` overlays are forbidden — open cards must never cover neighbours) with a `max-height .38s` transition.
- Cards enter with a staggered `fadeUp` animation (delay set inline by the engine).
- `.cheat-card` keeps `overflow:hidden` when closed so the body never peeks through.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md (SCHEMA.md → wiki → references → design notes)
  - Read references/cheat-sheet-selection.md — what belongs on a cheat sheet (frequent use,
    high mistake rate, high-density facts), what stays out, card anatomy
  - Identify 15-30 key concepts/syntax patterns/formulas to cover
  - Group into 3-6 topic categories (cat keys + labels)
  - Mark every theorem/formula/equation/constant card with kind:'formula'
  - Each card needs: title, summary, detail; formula cards also formula ($$…$$ + unicode)

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` —
    always read it first; the system prompt's Subject Theme section is only a fallback if the file is missing
  - Set the `← theme` vars in the copied CSS; base TOPIC_COLORS hues on the theme

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/cheat-sheet.css into <style>, set the theme vars
  - Copy assets/cheat-sheet.js into <script> verbatim
  - Build the skeleton with the fixed element IDs (catFilters, formulaToggle, cheatSearch, clearSearch, resultCount, cardGrid)
  - Fill in CARDS and TOPIC_COLORS with your designed content

STEP 4 — SELF-CHECK (each item must pass)
  - All element IDs referenced by the engine exist in the HTML
  - Every .cat in CARDS has a TOPIC_COLORS entry
  - Every kind:'formula' card has a non-empty formula field with $$ delimiters AND unicode fallback AFTER them
  - No card content is left as placeholder ("...") — every card is complete
  - Card count between 15 and 30
  - The CARDS array parses as valid JSON when copied to a .json file
  - #cardGrid uses columns (cascade), not display:grid; cards have min-height, not a fixed tall height

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="cheat", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```