# Template 4: Interactive Mind Map

## Purpose
Full interactive SVG-based concept map with D3.js. Collapsible tree, detail panel, search, zoom/pan.

## Structure
```
├── <head>
│   ├── Google Fonts (Inter via @import)
│   ├── D3.js via CDN <script src="https://d3js.org/d3.v7.9.0.min.js" integrity="sha384-3ZkyFNMhTj0I2TIpFtpD0K4H3I41KXy0FhbL3QpLMK4G6G6f6F71h3I4m3oV7U" crossorigin="anonymous">
│   ├── <style> (full CSS with custom properties, SVG styles, panel styles)
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> + .subtitle
│   │   ├── .controls (buttons: reset, expand all, collapse all, search toggle)
│   │   └── .badge (node count)
│   ├── <div id="map-container"> → <svg> → <g id="graph-g">
│   ├── <div class="panel-overlay" id="panelOverlay">
│   ├── <div class="detail-panel" id="detailPanel">
│   │   ├── .panel-header (> h2 + close btn)
│   │   ├── .panel-breadcrumb
│   │   ├── .panel-cat-bar (color bar)
│   │   ├── .panel-body
│   │   └── </div>
│   ├── <div class="search-box" id="searchBox">
│   │   ├── <input id="searchInput">
│   │   └── <span class="search-close">✕
│   ├── <div class="tooltip-float" id="tooltip">
│   └── <script>
│       ├── const DATA = nested object ↓
│       ├── const COLORS = { category: '#hex' }
│       ├── D3 tree layout, zoom behavior
│       ├── update(source) — render nodes + links with transitions
│       ├── openDetail(d) — slide panel, build content
│       ├── search/clear functions
│       └── init
```

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

## COLORS map
```javascript
const COLORS = {
  fundamentos: '#a78bfa',   // purple
  java: '#4fc1ff',          // blue
  // ... add per-topic colors as needed
};
```

## Node rendering
- Root: large circle (r=28) with gold stroke and glow
- Level 1: medium (r=22)
- Level 2+: small (r=16)
- All collapsed by default (depth>0), root children shown initially
- Click toggles collapse/expand + opens detail panel
- Icon/text in center of each circle via `getIcon(d)` map
- Labels below circles, wraps to multiple lines using `<tspan>`

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
Can also include `.code-block`, `.tag.*`, `.rel-box` for relationship data.

## Search functionality
- `/` key toggles search
- Highlights matching nodes with white stroke + glow
- Clears on close

## Controls
- Reset zoom: centers on root
- Expand all: shows all children recursively
- Collapse all: hides all except root's direct children
- Zoom: D3 zoom behavior with mouse wheel + drag

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Read SCHEMA.md for subject conventions
  - Read ALL wiki files (this is the ONE time you read everything)
  - Read subjects/{subject}/references/ for notes
  - Design the concept hierarchy as a tree structure
  - MAXIMUM 40-50 nodes total — mind maps with more become unreadable
  - Each leaf node needs: name, cat, desc (tooltip), detail (panel HTML content)
  - Group into categories matching COLORS
  - Design ALL content yourself

STEP 2 — THEME
  - Read `references/_theme.md` via `read_vault_file` (or use the colors from the system prompt's Subject Theme section)
  - The COLORS map must have keys matching all .cat values in data

STEP 3 — HTML FRAMEWORK
  - Include D3.js v7.9.0 from CDN with SRI integrity hash
  - Full CSS: custom properties, SVG styles (.link, .node-circle, .node-label)
  - Panel overlay + detail panel with slide animation
  - Search box overlay (/ to toggle)
  - Tooltip float

STEP 4 — JS STRUCTURE
  - Define DATA (nested hierarchy)
  - Define COLORS (category→color map)
  - D3: treeLayout().nodeSize([180, 260])
  - zoom behavior with d3.zoomIdentity
  - update() function: links enter/exit/merge + nodes enter/exit/merge with transitions
  - diagonal() path generator for curved links
  - getRadius(d), getColor(d), getIcon(d) helper functions
  - openDetail(d), closePanel() for detail panel
  - toggleSearch(), onSearch(), clearSearch() for search
  - expandAll(), collapseAll(), resetZoom() for controls
  - Keyboard shortcuts: Escape closes panel/search, / opens search

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag, and full HTML
  - Pass `tag` parameter (e.g. "mindmap")
  - Log to subjects/{subject}/wiki/log.md
```
