# Template 10: Diagram Labeling

## Purpose
Interactive labeling of a figure the model builds itself (SVG): numbered hotspots on the drawing, shuffled label chips, check/reveal/reset. Best for anatomy, machinery, physics setups, graphs with labeled parts (e.g. "partes de un DCL", "trayectoria del proyectil", "montaje del péndulo").

## Canonical boilerplate (copy, don't rewrite)

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/labeling.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/labeling.js')` → paste into `<script>`. **Fill in ONLY** the `SVG_MARKUP` and `LABELS` consts. Do not modify the engine functions.

HTML skeleton with the fixed element IDs the engine looks up:

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> — labeling.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   └── .sub — metadata line
│   ├── <div class="wrap">
│   │   ├── <div id="labelStatus" role="status" aria-live="polite">
│   │   ├── <div class="figure"><div id="labelSvg"></div></div>
│   │   ├── <div class="chips" id="labelChips"></div>
│   │   ├── .action-row
│   │   │   ├── <button id="labelCheck">Comprobar</button>
│   │   │   ├── <button id="labelReveal">Revelar</button>
│   │   │   ├── <button id="labelReset">Reiniciar</button>
│   │   │   └── <span id="labelScore">
│   └── <script> — labeling.js
```

## Data format

```javascript
const SVG_MARKUP = '<svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">' +
  '  <rect x="0" y="0" width="400" height="300" fill="#12121a" rx="12"/>' +
  '  <circle cx="200" cy="120" r="60" fill="#1f1f2c" stroke="#5b7fc4" stroke-width="2" data-hotspot="h1"/>' +
  '  <line x1="100" y1="220" x2="300" y2="220" stroke="#2a2a3a" stroke-width="3" data-hotspot="h2"/>' +
  '</svg>';

const LABELS = [
  { id:'l1', text:'Centro de masa', target:'h1' },
  { id:'l2', text:'Suelo', target:'h2' }
];
```

- Hotspots are any SVG element (`circle`, `rect`, `path`, `polygon`, `line`...) carrying `data-hotspot="h1"`. Badges are numbered 1..N in document order.
- The figure must be **unlabeled** — the answer text lives ONLY in `LABELS[].text`.
- `target` must match a `data-hotspot` id exactly, one label per hotspot.
- Build the SVG with `viewBox` (fixed logical size) — it scales to the container. Use theme hues for strokes/fills.
- 5–12 hotspots is the sweet spot.
- Math in label text uses the `$$LaTeX$$ fallback-text` convention (see the Mathematics section in SKILL.md).

## Behavior notes (engine-enforced, do not override)

- **Chip-first interaction**: a hotspot cannot be selected until a chip is selected; clicking a hotspot with no chip selected nudges ("Primero elige una etiqueta...") instead of erroring.
- Select a chip, then click its hotspot (either order works); clicking the selected chip/hotspot again removes the assignment.
- **While placing, no correct/wrong marks appear** — green/red feedback happens only on "Comprobar" (or "Revelar"), so misplaced chips stay neutral and retryable.
- **Label text is drawn OUTSIDE the shape** with a leader line and a dark halo, so it never covers the drawing; near the edges the label flips to the opposite side automatically, and consecutive labels stagger vertically to avoid overlap.
- "Comprobar" validates: green ring + green chip for correct, red flash for wrong (wrong ones stay visible to retry). Score reads "X / N correctas".
- "Revelar" shows the correct text at every hotspot.
- Hotspot elements with no `<circle>`/`<text>` children are fine — badges are appended by the engine.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md
  - Choose ONE figure that carries 5-12 nameable parts from the wiki
  - Sketch the figure first in the design note (parts + relative positions + viewBox)
  - Write the SVG by hand: background, outlines, fills — readable at 860px width

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first
  - Set the `← theme` vars in the copied CSS; use theme hues inside the SVG

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/labeling.css into <style>, set the theme vars
  - Copy assets/labeling.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in SVG_MARKUP (a JS string) and LABELS

STEP 4 — SELF-CHECK (each item must pass)
  - Every data-hotspot id has exactly one LABELS entry with matching target, and vice versa
  - The SVG has a viewBox and no labels baked in
  - SVG_MARKUP is a valid JS string (escaped quotes); LABELS parses as valid JSON
  - The figure is meaningful standalone (recognizable without its labels)
  - Every formula follows `$$LaTeX$$ fallback-text` (never bare LaTeX without fallback)

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="label", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```
