# Template 8: Interactive Timeline

## Purpose
Chronological timeline with era bands, category/era filters, search, and a detail panel. Best for history, literature periods, scientific milestones, process evolution (e.g. "hitos de la mecánica", "evolución del modelo atómico", "etapas de un movimiento").

## Canonical boilerplate (copy, don't rewrite)

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/timeline.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/timeline.js')` → paste into `<script>`. **Fill in ONLY** the `EVENTS`, `ERAS` and `CATEGORY_COLORS` consts. Do not modify the engine functions.

HTML skeleton with the fixed element IDs the engine looks up:

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> — timeline.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   └── .sub — metadata line
│   ├── <div class="wrap">
│   │   ├── .controls
│   │   │   ├── .filter-row#eraFilters (era buttons)
│   │   │   ├── .filter-row#catFilters (category buttons)
│   │   │   ├── .search-row (#tlSearch input + #tlReset button)
│   │   ├── .tl-count (<span id="tlCount">)
│   │   ├── .tl-layout
│   │   │   ├── #tlRail (floating panel: color-coded segments + dots + year labels, filled by engine)
│   │   │   └── #tlList (event rows, filled by engine)
│   ├── #detailOverlay > #detailPanel
│   │   ├── #detailTitle, #detailChips, #detailYear, #detailBody
│   │   └── #detailClose (button)
│   └── <script> — timeline.js
```

## Data format

```javascript
const EVENTS = [
  { id:'e1', year:1905, era:'mecanica', eraLabel:'Mecánica',
    cat:'concepto', title:'...', summary:'Una frase',
    detail:'<p>HTML expansion shown in the detail panel</p>' }
];

const ERAS = [ { key:'mecanica', label:'Mecánica', color:'rgba(91,127,196,0.25)' } ];

const CATEGORY_COLORS = { concepto:'#5b7fc4', formula:'#fbbf24' };
```

- `year` must be a number; events sort by year, oldest first.
- `era`/`eraLabel`: every `era` key MUST exist in `ERAS` (ordered oldest-first). The optional `color` tints the era band on the rail.
- `cat`: every category key MUST have a `CATEGORY_COLORS` entry (max 4 categories). Each category color is also used for the rail's line segments.
- Math in `summary`/`detail` uses the `$$LaTeX$$ fallback-text` convention (see the Mathematics section in SKILL.md).

## Behavior notes (engine-enforced, do not override)

- The rail is a **floating glass panel stuck to the viewport**: it stays visible (top:16px) while the event cards scroll with the page beside it; it never shows its own scrollbar. It sits in its own 150px grid column, so it never overlaps the cards or the header/filters.
- **The rail line is color-coded by era (topic)**: one colored segment per era spanning the era's year range. Era segments take `era.color` when it is a hex value, otherwise the theme's category colors (cycled by era order) — pull distinct hues from the theme so topics read apart.
- **A rounded-year axis runs beside the line**: steps of 1/2/5×10^k chosen from the year span (~6 divisions, e.g. 1604–1843 → 1600·1650·1700·1750·1800·1850; a 5-million-year span → divisions every 1,000,000). Each division is a small horizontal tick crossing the line with its rounded year label to the LEFT of the line.
- Dots sit at their proportional year position with the **event year label to the RIGHT of each dot**; labels are placed to stay aligned with their dot, moving only as much as needed to avoid overlapping each other (bidirectional resolution).
- **Events sharing the same year fan out into a horizontal cluster** so no two dots overlap; the cluster is clickable as a unit and opens the detail of the first event.
- Filters (era + category) and search combine; the count line updates.
- Detail panel is a modal: Escape or the close button dismisses it; body scroll locks while open.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md (SCHEMA.md → wiki → references → design notes)
  - Pick a scope with a real chronological span: 8-20 events across 2-4 eras
  - Each event needs: {id, year, era, eraLabel, cat, title, summary, detail}
  - detail must be substantive (definitions, formulas, implications) — not filler
  - Write ALL content yourself from the wiki pages

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first
  - Set the `← theme` vars in the copied CSS; pick CATEGORY_COLORS hues from the theme

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/timeline.css into <style>, set the theme vars
  - Copy assets/timeline.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in EVENTS, ERAS, CATEGORY_COLORS with your designed content

STEP 4 — SELF-CHECK (each item must pass)
  - Every era used by an event exists in ERAS; every cat has a CATEGORY_COLORS entry
  - Every id is unique; every year is a number; events cover at least 2 eras
  - The consts parse as valid JSON when copied to a .json file (no trailing commas)
  - detail text contains no unescaped quotes or stray </script>
  - Every formula follows `$$LaTeX$$ fallback-text` (never bare LaTeX without fallback)

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="timeline", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```
