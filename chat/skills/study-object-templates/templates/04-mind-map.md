# Template 4: Interactive Mind Map

## Purpose
Full interactive SVG-based concept map with D3.js. **Radial collapsible tree** (branches expand outward around the root for spatial reading), detail panel, search (names + descriptions), zoom/pan.

## Canonical boilerplate (copy, don't rewrite)

The JS engine and CSS are canonical files — **copy them verbatim** into the generated HTML:

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/mindmap.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/mindmap.js')` → paste into `<script>`. **Fill in ONLY** the `DATA` and `COLORS` (and optionally `ICONS`) consts at the top. Do not modify the engine functions.

The engine expects these element IDs — keep them exact: `map-container`, `panelOverlay`, `detailPanel`, `panelTitle`, `panelBreadcrumb`, `panelCatBar`, `panelBody`, `panelClose`, `searchBox`, `searchInput`, `searchClose`, `tooltip`, `resetBtn`, `expandAllBtn`, `collapseAllBtn`, `searchToggleBtn`.

## HTML skeleton

```
├── <head>
│   ├── Google Fonts (Inter via @import)
│   ├── D3.js v7 from CDN (URL + SRI below)
│   ├── <style> — mindmap.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> + .subtitle
│   │   ├── .controls (resetBtn, expandAllBtn, collapseAllBtn, searchToggleBtn)
│   │   └── .badge (node count)
│   ├── <div id="map-container">
│   ├── <div class="panel-overlay" id="panelOverlay">
│   ├── <div class="detail-panel" id="detailPanel">
│   │   ├── .panel-header (> h2#panelTitle + #panelClose btn)
│   │   ├── .panel-breadcrumb#panelBreadcrumb
│   │   ├── .panel-cat-bar#panelCatBar (4px color strip)
│   │   ├── .panel-body#panelBody
│   │   └── </div>
│   ├── <div class="search-box" id="searchBox">
│   │   ├── <input id="searchInput" placeholder="Buscar concepto…">
│   │   └── <span class="search-close" id="searchClose">✕
│   ├── <div class="tooltip-float" id="tooltip">
│   └── <script src="https://d3js.org/d3.v7.min.js" integrity="sha384-CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i" crossorigin="anonymous"></script>
│   └── <script> — mindmap.js
```

**D3 CDN**: use exactly `https://d3js.org/d3.v7.min.js` with the SRI hash above. Do NOT use `d3.v7.9.0.min.js` — that file returns 404 on d3js.org, and an invalid/mismatched SRI hash makes the browser block the script (blank map, no error). The versionless `d3.v7.min.js` URL always serves the current v7.

## Data format

```javascript
const DATA = {
  name: 'Subject Name',
  cat: 'root',
  children: [
    {
      name: 'Topic',
      cat: 'topic-key',
      children: [
        {
          name: 'Concept',
          cat: 'topic-key',
          desc: 'Short description (appears in tooltip)',
          detail: '<div class="detail-section"><h3>Title</h3><p>HTML content...</p></div>'
        }
      ]
    }
  ]
}
```

```javascript
const COLORS = {
  fundamentos: '#a78bfa',   // one entry per .cat value used in DATA
};
const ICONS = {};            // optional: per-cat emoji overrides
```

## Behavior built into the engine
- Radial layout with **FIXED positions**: a single D3 tree pass over the full tree computes every node's angle/radius into `posMap`; nodes never move again. Expanding/collapsing a branch only reveals/hides nodes — the rest of the map stays put (no re-layout jitter).
- Links are **straight lines** (`<line>` elements) between parent/child positions, tinted with the child's category color (`.style('stroke', d => getColor(d[1]))`)
- Rings are **SVG circles inside the zoomed group** (`RING_FRACS = [0.25, 0.5, 0.75, 1]`, class `ring`) centered on the root — they follow the map when zooming/panning
- Root: large circle (r=30) with gold fill; Level 1: r=22; Level 2+: r=15
- Node colors come from the `COLORS` map — the engine sets the CSS `color` on each node and the circle/icon use `fill:currentColor`, so every node is tinted by its category
- **Double-click zoom is disabled** (`dblclick.zoom` nulled) — it fights with node clicks; zoom is wheel + drag only
- **Every node glows subtly in its own color** (large soft radius via `drop-shadow` + `color-mix`, ~40% strength); hover boosts the glow; the root breathes with a gentle pulse (`.root-node` class — never select the root with `:first-child`)
- Entrance animation is **scoped to the `.node-enter` class** (staggered, `translate`-property keyframes) and the class is **removed on `animationend`** — expanding/collapsing a branch animates ONLY the branch's nodes, never the rest of the map
- **Whole-map operations are instant, not animated**: clicking the root (it toggles everything) and the expand-all/collapse-all buttons pass `animate:false` to `update()` — dozens of nodes appear/disappear at once without re-animating the entire map
- All nodes deeper than level 1 collapsed by default (root children visible)
- Click toggles collapse/expand; the detail panel opens only when the node has `desc` or `detail` content (branch-only nodes just collapse, no empty panel)
- Labels are horizontal, anchored by map side (`isRightSide` → `text-anchor` start/end) and vertically centered on the node; they are wrapped into tspans (the engine never sets `.text()` on the label before wrapping — that double-renders the name)
- Search (`/` to open, Escape closes): matches node names AND `desc` descriptions; highlights matching nodes with white stroke + glow
- Controls: reset zoom (centers on root, fits viewport), expand all, collapse all (collapses to the topic level so it always visibly does something)
- Zoom: D3 zoom behavior with mouse wheel + drag
- Tooltip shows `desc` on hover; detail panel shows breadcrumb + desc + detail HTML

## Detail panel content
```html
<div class="detail-section">
  <h3>Section Title</h3>
  <p>Content...</p>
</div>
<div class="detail-section">
  <h3>Subtopics</h3>
  <ul><li>Item 1</li>...</ul>
</div>
```
Can also include `.code-block`, `.tag.*`, `.rel-box` for relationship data (styled by mindmap.css).

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md (SCHEMA.md → wiki → references → design notes)
  - Design the concept hierarchy as a tree structure
  - MAXIMUM 40-50 nodes total — mind maps with more become unreadable
  - Depth: 4 levels of nesting are good (root > tema > subtema > concepto); ≥ 25 nodes
  - Put rich detail in leaf nodes; every leaf needs: name, cat, desc, detail (panel HTML)
  - desc must be INFORMATIVE — ≥ 100 characters on average (tooltip text)
  - Every .cat value must have a COLORS entry — pick hues from the subject theme
  - Design ALL content yourself

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first; the system prompt's Subject Theme section is only a fallback if the file is missing
  - Set the `← theme` vars in the copied CSS; base COLORS hues on the theme

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/mindmap.css into <style>, set the theme vars
  - Include the D3 CDN script with the exact URL + SRI hash above
  - Copy assets/mindmap.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in DATA, COLORS, ICONS with your designed hierarchy

STEP 4 — SELF-CHECK (each item must pass)
  - D3 script tag uses d3.v7.min.js + the exact SRI hash
  - All element IDs referenced by the engine exist in the HTML
  - The DATA object parses as valid JSON when copied to a .json file
  - Every .cat in DATA has a COLORS entry
  - Node count between 25 and 50; nesting depth ≥ 3 (4 levels with root)
  - Average desc length ≥ 100 characters
  - No detail panel content is left as placeholder ("...") — every leaf is complete
  - No dblclick zoom handler; rings are SVG (class "ring"), not CSS backgrounds
  - Links are <line> elements (straight), not curved paths

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag, and full HTML
  - Pass `tag` parameter (e.g. "mindmap")
  - Log to subjects/{subject}/wiki/log.md
```
