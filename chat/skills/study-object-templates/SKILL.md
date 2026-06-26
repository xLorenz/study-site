---
name: study-object-templates
title: "Study Object Templates — HTML Generation Reference"
description: "Canonical reference for the 7 HTML template formats (static mock exam, solutions, interactive flashcards, mind maps, cheat sheets, formula decks + interactive exam with toggle answers). Used by study-professor when building interactive study aids."
---

# Study Object Templates

This skill describes the **6 canonical HTML template formats** stored at `~/.hermes/`. The `study-professor` skill points here when generating study objects — **always load this skill** (`skill_view(name='study-object-templates')`) before generating any new study object.

## Template Files

| File | Type | Size | Interactivity |
|------|------|------|---------------|
| `parcial_practica_POO.html` | Static mock exam (theory + practice) | 484 lines / 29KB | None (static) |
| `Parcial_Practica2_POO.html` | Static mock exam (design patterns + SOLID) | 552 lines / 32KB | None (static) |
| `soluciones_parcial.html` | Solutions document | 1007 lines / 78KB | None (static) |
| `flashcards_poo.html` | Interactive MCQ quiz | 1269 lines / 55KB | Full JS |
| `flashcards_poo_hard.html` | Hard-mode interactive MCQ quiz | 1279 lines / 65KB | Full JS |
| `mapa_conceptual_poo.html` | Interactive SVG mind map | 1676 lines / 80KB | Full JS (D3.js) |

---

## Common Patterns (ALL templates)

### Color scheme
- Background: `#0a0a0f` to `#0f0f13` — very dark
- Text: `#e2e2e8`, secondary `#6a6a7a` / `#b0b0c0`
- Surfaces: `#111118`, `#18181c`, `#1f1f2a`
- Borders: `#1e1e2a`, hover `#2a2a3a`
- Accent varies by subject/theme (see `references/_theme.md` or the Subject Theme section in the system prompt)

### Fonts
- **Body**: `'Inter', system-ui, -apple-system, sans-serif`
- **Code**: `'JetBrains Mono', 'Fira Code', monospace`
- Google Fonts loaded via `@import url()` or `<link>` from `fonts.googleapis.com`

### Syntax highlighting classes (for all code blocks)
```css
.kw  { color: #c586c0; }  /* keywords (new, if, class, etc.) */
.type { color: #4fc1ff; } /* types (String, int, Animal) */
.str { color: #ce9178; }  /* strings */
.cm  { color: #6a9955; }  /* comments */
.num-c { color: #b5cea8; } /* numbers */
.ann  { color: #dcdcaa; } /* annotations */
.fn   { color: #dcdcaa; } /* function names (soluciones only) */
```

### Code block pattern
```html
<div class="code"><pre>
<span class="kw">public</span> <span class="type">String</span> foo() { ... }
</pre></div>
```
Or in interactive flashcards (where code appears in questions):
```html
<div class="code-block">
<span class="type">Animal</span> a = <span class="kw">new</span> <span class="type">Perro</span>();
</div>
```

### Responsive
- `@media (max-width: 480px)` or `@media (max-width: 640px)` breakpoints
- Font-size reduction, padding adjustments
- No fixed pixel widths for layout (container `max-width` only)

### Print
- `@media print` hides interactive elements, inverts backgrounds to white
- Code blocks get light gray background

---

## TEMPLATE 1: Static Mock Exam (`parcial_practica_POO.html`, `Parcial_Practica2_POO.html`)

### Purpose
Print-friendly static exam with theory questions and coding exercises. No JS interaction — just present the content.

### Structure
```
├── <head>
│   ├── Google Fonts (Inter)
│   ├── <style> — full CSS
│   └── </head>
├── <body>
│   ├── <div class="container">
│   │   ├── <h1> — gradient title
│   │   ├── <p class="subtitle"> — metadata (duration, topics)
│   │   ├── <div class="section">  ← repeat per block
│   │   │   ├── <h2> block title + <span class="badge">points</span>
│   │   │   ├── <p class="tip"> — instructions
│   │   │   ├── <h3> exercise title  ← optional, only if grouped
│   │   │   ├── <div class="question">  ← repeat per question
│   │   │   │   ├── <p><span class="num">1.</span> question text...</p>
│   │   │   │   └── <div class="alert"> — extra commentary</div>
│   │   │   └── </div>
│   │   └── </div>
│   │   └── <div class="footer">
│   └── </body>
```

### CSS details
- `.section` card: `background: #18181c; border: 1px solid #27272a; border-radius: 12px; padding: 1.5rem;`
- `.question` block: `border-left: 3px solid #3b3b45; padding-left: 0.75rem;`
- `.alert` box: themed background with accent border, for hints/comments
- `.badge`: small rounded pill for point values
- Title: gradient `linear-gradient(135deg, accent1, accent2)` with `-webkit-background-clip: text; -webkit-text-fill-color: transparent`

### Build steps (STEP-BY-STEP PROMPT)

```
STEP 1 — SCHEMA & CONTENT DESIGN
  - Read subjects/{subject}/SCHEMA.md for conventions (including language: wiki pages follow the raw sources' language)
  - Read ALL .md files in subjects/{subject}/wiki/ to understand content
  - Read subjects/{subject}/references/ for any existing notes
  - Design exam content: decide theory questions (15-20 for full exam) and practical exercises (4-6)
  - Each question needs: question text, difficulty indicator, point value
  - Group by theme blocks (Theory, Practice, Design Patterns, UML, etc.)
  - Write ALL question content yourself — no delegation

STEP 2 — THEME LOOKUP
  - Read `references/_theme.md` via `read_vault_file` (or use the colors from the system prompt's Subject Theme section)
  - Title gradient = linear-gradient(135deg, primary, secondary)
  - Section h2 color = secondary (or accent)
  - Alert border-color = accent with transparency

STEP 3 — HTML STRUCTURE
  - Write self-contained HTML file
  - Google Fonts: @import url('Inter')
  - CSS: all 4 common patterns above (dark theme, code highlighting, responsive, print)
  - Container max-width: 900px
  - One .section per themed block
  - Each question in .question with .num for numbering
  - Code in .code > pre with syntax highlighting spans
  - Alerts in .alert for side-notes

STEP 4 — SAVE & LOG
  - Call `write_study_object` with filename, tag, and full HTML
  - Pass `tag` parameter (e.g. "mock", "cheat", "mindmap", "formula", "flash", "exam")
  - Log to subjects/{subject}/wiki/log.md
```

---

## TEMPLATE 2: Solutions Document (`soluciones_parcial.html`)

### Purpose
Comprehensive answer key with navigation, Q&A pairs, cross-references.

### Structure
```
├── <head> (similar to mock exam)
├── <body>
│   ├── <div class="container">
│   │   ├── <h1> + <p class="subtitle">
│   │   ├── <div class="nav">  ← anchor links
│   │   │   ├── <a href="#B1">Bloque I</a>
│   │   │   └── ...
│   │   ├── <div class="section" id="B1">  ← repeat per block
│   │   │   ├── <h2> block title
│   │   │   ├── <div class="qa">  ← repeat per answer
│   │   │   │   ├── <div class="q">Question text</div>
│   │   │   │   ├── <div class="a">Answer text</div>
│   │   │   │   └── <div class="code">...</div>
│   │   │   └── </div>
│   │   └── </div>
│   │   └── <div class="footer">
│   └── </body>
```

### Unique features
- `.nav` with anchor links to section IDs — navigation bar at top
- `.qa` pair pattern: `.q` gold (`#fbbf24`), `.a` green (`#bef264`)
- Can include `h4` sub-headers within sections
- Tags: `.tag.purple`, `.tag.blue`, `.tag.green`, `.tag.orange`, `.tag.red`, `.tag.pink`, `.tag.teal`
- Print-friendly: explicit `@media print` color overrides

### Build steps (STEP-BY-STEP PROMPT)

```
STEP 1 — CONTENT DESIGN
  - Read SCHEMA.md for subject conventions (including language: wiki content follows the raw sources' language)
  - Read all wiki files
  - Read existing design notes from subjects/{subject}/references/ for context
  - For each question in the exam being solved, write:
    a) The question (formatted as .q)
    b) The complete answer (formatted as .a)
    c) Code examples where relevant (syntax-highlighted .code blocks)
  - Add tags for topic classification

STEP 2 — THEME LOOKUP (same as mock exam)

STEP 3 — HTML STRUCTURE
  - Add .nav at top with anchor links for each block
  - Each .section gets id="B1", "B2", etc.
  - Use .qa > .q (question) + .a (answer) pattern
  - Include .alert boxes for tips/extra info
  - Code examples in .code > pre with syntax spans

STEP 4 — SAVE & LOG (same pattern)
```

---

## TEMPLATE 3: Interactive Flashcards / Quiz (`flashcards_poo.html`, `flashcards_poo_hard.html`)

### Purpose
Full interactive multiple-choice quiz with feedback, progress tracking, confetti on correct answers, keyboard navigation.

### Structure
```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> (CSS custom properties, card, options, feedback)
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   ├── .stats (✅ correct, ❌ wrong, 📊 total)
│   │   └── .progress-bar-wrap > .progress-bar > .fill
│   ├── <main> → <div id="cardContainer">
│   ├── .bottom-bar (prev, counter, reset buttons)
│   ├── <canvas id="confetti-canvas">
│   └── <script>
│       ├── const QUESTIONS = [...]
│       ├── state object (questions, currentIdx, history, counts)
│       ├── initGame() — shuffle, reset state
│       ├── renderCard(idx, anim) — build DOM for current card
│       │   └── Options as buttons with letter badges
│       ├── handleAnswer(qIdx, selected) — check, feedback, confetti
│       ├── nextCard() — find next unanswered, advance
│       ├── goBack() — previous card (undo history)
│       ├── renderEmpty() — completion state
│       ├── confettiBurst() — canvas particle animation
│       ├── Event listeners: keyboard arrows, buttons
│       └── initGame()
```

### Data format
```javascript
const QUESTIONS = [
  {
    id: 'f1',
    tag: 'fundamentos',      // category key
    tagLabel: 'Fundamentos',  // display label
    question: 'HTML question text with <code>inline code</code> or <div class="code-block">...</div>',
    options: ['Option A', 'Option B', 'Option C', 'Option D'],
    correct: 2,               // index of correct option (0-based)
    explanation: 'HTML explanation shown after answering',
    detail: 'Extra detail shown below explanation'
  }
]
```

### State management
```javascript
const state = {
  questions: [],           // shuffled copy
  currentIdx: 0,
  history: [],             // {qIdx, selected, correct}[]
  correctCount: 0,
  wrongCount: 0,
  seenCount: 0,
  answered: false,
  exhausted: false
}
```

### CSS custom properties
```css
:root {
  --bg: #0a0a0f; --surface: #111118; --surface2: #181822; --surface3: #1f1f2c;
  --border: #1e1e2a; --border2: #2a2a3a;
  --text: #e2e2ec; --text2: #b0b0c0; --text3: #6a6a7a;
  --accent: #a78bfa; --accent2: #7c3aed;
  --gold: #fbbf24; --green: #4ade80; --red: #f87171;
  --blue: #4fc1ff; --orange: #fb923c; --pink: #f472b6; --teal: #2dd4bf;
  --radius: 14px; --radius-sm: 8px;
  --transition: 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}
```

### Hard mode differences
- Accent: `#fb923c` (orange) instead of `#a78bfa` (purple)
- Added `.badge-hard` element with "HARD MODE" label
- Header max-width: 700px (vs 640px)
- Content is harder/different questions but same data format

### Build steps (STEP-BY-STEP PROMPT)

```
STEP 1 — CONTENT DESIGN
  - Read SCHEMA.md for subject conventions (including language: wiki content follows the raw sources' language)
  - Read ALL wiki files to extract key concepts
  - Read subjects/{subject}/references/ for notes
  - Design 30-50 questions MAX (to avoid bloated HTML file)
  - Each question needs: {id, tag, tagLabel, question, options[4], correct, explanation, detail}
  - Cover all major topic areas from the wiki
  - Write ALL question content yourself — the point is your understanding drives the questions

STEP 2 — THEME
  - Read `references/_theme.md` via `read_vault_file` (or use the colors from the system prompt's Subject Theme section)
  - Flashcards use accent for option hover, correct indicator, next-button

STEP 3 — SETUP FRAMEWORK
  - Start with the full CSS framework (custom properties + all card/option/feedback styles)
  - Copy the state management boilerplate (initGame, renderCard, handleAnswer, nextCard, goBack)
  - Copy the confetti canvas animation (reuse verbatim)
  - Copy event listeners (keyboard arrows, prev/reset buttons)
  - Fill in the QUESTIONS array with your designed content

STEP 4 — ADJUSTMENTS
  - Options array must be exactly 4 elements
  - Question text can include inline <code> and <div class="code-block"> with syntax spans
  - Detail field should expand on the topic, include more examples
  - For HARD mode: use orange accent, more challenging content, add "HARD MODE" badge

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag, and full HTML
  - Pass `tag` parameter (e.g. "flash")
  - Log to subjects/{subject}/wiki/log.md
```

---

## TEMPLATE 4: Interactive Mind Map (`mapa_conceptual_poo.html`)

### Purpose
Full interactive SVG-based concept map with D3.js. Collapsible tree, detail panel, search, zoom/pan.

### Structure
```
├── <head>
│   ├── Google Fonts (Inter via @import)
│   ├── D3.js via CDN <script src="https://d3js.org/d3.v7.min.js">
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

### Data format
```javascript
const DATA = {
  name: 'Programación Orientada a Objetos',
  cat: 'root',
  children: [
    {
      name: 'Fundamentos',
      cat: 'fundamentos',    // matches COLORS key
      children: [
        {
          name: 'Encapsulamiento',
          cat: 'fundamentos',
          desc: 'Descripción corta (aparece en tooltip)',
          detail: '<div class="detail-section"><h3>Título</h3><p>Contenido HTML...</p></div>'
        }
      ]
    }
  ]
}
```

### COLORS map
```javascript
const COLORS = {
  fundamentos: '#a78bfa',   // purple
  java: '#4fc1ff',          // blue
  jcf: '#4ade80',           // green
  patrones: '#fb923c',      // orange
  solid: '#fbbf24',         // gold
  swing: '#f472b6',         // pink
  uml: '#2dd4bf',           // teal
  avanzado: '#f87171'       // red
};
```

### Node rendering
- Root: large circle (r=28) with gold stroke and glow
- Level 1: medium (r=22)
- Level 2+: small (r=16)
- All collapsed by default (depth>0), root children shown initially
- Click toggles collapse/expand + opens detail panel
- Icon/text in center of each circle via `getIcon(d)` map
- Labels below circles, wraps to multiple lines using `<tspan>`

### Detail panel content
```html
<div class="detail-section">
  <h3>Section Title</h3>
  <p>Content...</p>
</div>
<div class="detail-section">
  <h3>Subtemas</h3>
  <ul><li>Item 1</li>...</ul>
</div>
```
Can also include `.code-block`, `.tag.*`, `.rel-box` for relationship data.

### Search functionality
- `/` key toggles search
- Highlights matching nodes with white stroke + glow
- Clears on close

### Controls
- Reset zoom: centers on root
- Expand all: shows all children recursively
- Collapse all: hides all except root's direct children
- Zoom: D3 zoom behavior with mouse wheel + drag

### Build steps (STEP-BY-STEP PROMPT)

```
STEP 1 — CONTENT DESIGN
  - Read SCHEMA.md for subject conventions (including language: wiki content follows the raw sources' language)
  - Read ALL wiki files (this is the ONE time you read everything)
  - Read subjects/{subject}/references/ for notes
  - Design the concept hierarchy as a tree structure
  - MAXIMUM 40-50 nodes total — mind maps with more become unreadable
  - Each leaf node needs: name, cat, desc (tooltip), detail (panel HTML content)
  - Group into categories matching COLORS
  - Design ALL content yourself: descriptions, explanations, code examples for detail panel

STEP 2 — THEME
  - Read `references/_theme.md` via `read_vault_file` (or use the colors from the system prompt's Subject Theme section)
  - The COLORS map must have keys matching all .cat values in data

STEP 3 — HTML FRAMEWORK
  - Include D3.js v7 from CDN: <script src="https://d3js.org/d3.v7.min.js">
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

---

## TEMPLATE 7: Interactive Exam with Toggle Answers

### Purpose
Long-form comprehensive multi-topic exam with per-exercise show/hide answer buttons. Each exercise includes sub-questions and a detailed step-by-step solution hidden behind a toggle. More comprehensive than a static mock exam — designed for multi-topic integration (e.g. "all topics from prácticas 1–7"). Dark theme, interactive answer revealers.

### Structure
```html
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via @import)
│   ├── <style> — dark theme, exercise cards, toggle buttons, answer boxes, print
│   └── </head>
├── <body>
│   ├── <div class="container">
│   │   ├── <h1> — gradient title
│   │   ├── <p class="subtitle"> — metadata (duration, exercise count)
│   │   ├── <div class="toc">
│   │   │   └── <ol> — 2-column numbered TOC with topic tags per exercise
│   │   ├── <div class="exercise" id="e1">  ← repeat per exercise
│   │   │   ├── <div class="exercise-header">
│   │   │   │   ├── <div class="exercise-number"> — Ejercicio N — Topic Name
│   │   │   │   └── <div class="exercise-topics">
│   │   │   │       └── <span class="topic-tag.{type}"> — colored pill badges
│   │   │   ├── <div class="exercise-body">
│   │   │   │   ├── <p> problem statement
│   │   │   │   ├── <div class="data"> — data block (gold highlights)
│   │   │   │   ├── <div class="sub-question">  ← repeat per sub-question
│   │   │   │   │   └── <strong>a)</strong> question text
│   │   │   │   ├── <button class="btn-answer"> — toggle button
│   │   │   │   └── <div class="answer-box" id="ansN">
│   │   │   │       ├── <h4>RESOLUCIÓN
│   │   │   │       ├── <div class="step"> — one per sub-question
│   │   │   │       │   ├── <strong>step label</strong>
│   │   │   │       │   └── <div class="result"> — final result (accent color)
│   │   │   │       └── </div>
│   │   │   └── </div>
│   │   └── </div>
│   │   └── <div class="footer"> — attribution
│   └── </body>
├── <script>
│   └── function toggleAnswer(id) { ... }
└── </html>
```

### CSS framework

```css
:root {
  --bg: #0a0a0f; --surface: #111118; --surface2: #18181c; --surface3: #1f1f2a;
  --border: #1e1e2a; --border2: #2a2a3a;
  --text: #e2e2e8; --text2: #b0b0c0; --text3: #6a6a7a;
  --primary: #4fc1ff; --secondary: #a78bfa; --accent: #2dd4bf;
  --gold: #fbbf24; --green: #4ade80; --red: #f87171; --orange: #fb923c;
  --radius: 12px; --radius-sm: 8px;
}
```

### Key class patterns

- **`.exercise`**: card with `border-radius: var(--radius)` and `overflow: hidden`
- **`.exercise-header`**: `background: var(--surface2)`, contains number + topic tags
- **`.exercise-body`**: `padding: 1.5rem` — holds statements, data, sub-questions
- **`.data`**: `background: var(--surface2)`, gold `strong` for numerical data
- **`.formula-box`**: `border-left: 3px solid var(--primary)`, monospace, for circuit/config descriptions
- **`.sub-question`**: `border-left: 2px solid var(--border)`, `padding-left: 1.2rem`, staggered appearance
- **`.btn-answer`**: toggle button with show/hide state; `.showing` class when answer is visible (green border)
- **`.answer-box`**: hidden by default (`display: none`), visible with `.visible` class (`display: block` + fadeIn animation)
- **`.answer-box .step`**: individual sub-question resolution, separated by `border-bottom`
- **`.answer-box .result`**: final numeric/vector answer in `JetBrains Mono` with accent green color

### Topic tags (pill badges)

```css
.topic-tag.electro    { border-color: #4fc1ff44; color: #4fc1ff; }  /* electric field */
.topic-tag.potential  { border-color: #a78bfa44; color: #a78bfa; }  /* potential */
.topic-tag.work       { border-color: #2dd4bf44; color: #2dd4bf; }  /* force/motion/work */
.topic-tag.conductor  { border-color: #fbbf2444; color: #fbbf24; }  /* conductors */
.topic-tag.gauss      { border-color: #4ade8044; color: #4ade80; }  /* Gauss */
.topic-tag.circuit    { border-color: #fb923c44; color: #fb923c; }  /* circuits */
.topic-tag.capacitor  { border-color: #f8717144; color: #f87171; }  /* capacitors */
.topic-tag.magnetic   { border-color: #a78bfa44; color: #a78bfa; }  /* magnetism */
```

### Toggle answer JavaScript (minimal, always the same)

```javascript
function toggleAnswer(id) {
  const box = document.getElementById(id);
  const btn = box.previousElementSibling;
  box.classList.toggle('visible');
  btn.classList.toggle('showing');
  btn.textContent = box.classList.contains('visible')
    ? '📕 Ocultar respuesta'
    : '📖 Mostrar respuesta';
}
```

No dependencies, no state management, no confetti. Each exercise has its own independent toggle.

### Content design rules

1. **Select the hardest/comprehensive exercises** from each topic area — not the simplest ones
2. **Cover ALL requested topics** — don't skip any, even if some have fewer candidate exercises
3. **Each exercise ≈ 4-5 sub-questions** building from basic calculation to synthesis/extrapolation
4. **Include a `data` block** with all constants at the top of each exercise
5. **Answers must be step-by-step** with the final result highlighted in `.result` blocks
6. **No topics outside the requested set** — if the user specified a list, stick to it strictly
7. **Exercises should be multi-topic where natural** (e.g. Gauss + conductors, potential + work, magnetic force + Ampere)

### Build steps (STEP-BY-STEP PROMPT)

```markdown
STEP 1 — CONTENT DESIGN
  - Read ALL raw practice files (not just wiki summaries) from subjects/{subject}/raw/
  - Read existing design notes from subjects/{subject}/references/ for context
  - For each topic the user requested, identify the 1-2 hardest problems in that practice file
  - Look for exercises that combine multiple concepts (e.g. "cascarón esférico + Gauss + densidad")
  - Design 1 exercise per topic cluster (or combine closely related topics into 1 exercise)
  - Each exercise: 4-5 sub-questions (a, b, c, d, e) building in complexity
  - Each exercise: include a <div class="data"> block with all given constants
  - Each sub-question: write a complete step-by-step solution in advance

STEP 2 — THEME & HTML
  - Follow the exact CSS framework above (dark theme, exercise cards, toggle buttons)
  - Use topic tag pills matching the topic-color map
  - Container max-width: 960px
  - Add `.formula-box` for describing circuit topologies or configuration text

STEP 3 — ANSWER TOGGLES
  - Each exercise gets a unique answer box id: `ans1`, `ans2`, etc.
  - Each answer box is a sibling of the toggle button
  - Answers use `.step` per sub-question, `.result` for numeric/vector results
  - Include the JavaScript toggle function in a <script> tag at the bottom

STEP 4 — SAVE & LOG
  - Call `write_study_object` with filename, tag, and full HTML
  - Log to subjects/{subject}/wiki/log.md
```

---


## Template Selection Guide

When the user asks for a study object, pick by type keyword:

| User says | Template | File name pattern | Tag suggestion |
|-----------|----------|-------------------|----------------|
| "mock exam", "parcial", "practice exam" | Static Mock Exam | `{slug}-v{N}.html` | `mock` |
| "solutions", "answer key", "solucionario" | Solutions Document | `{slug}-v{N}.html` | `solutions` |
| "flashcards", "flash", "quiz", "mcq" | Interactive Flashcards | `{slug}-v{N}.html` | `flash` |
| "mind map", "mapa conceptual", "concept map" | Interactive Mind Map | `{slug}-v{N}.html` | `mindmap` |
| "cheat sheet", "reference card", "resumen" | Static format (similar to exam section layout) | `{slug}-v{N}.html` | `cheat` |
| "formula deck", "formulas" | Static format (similar to solutions Q&A) | `{slug}-v{N}.html` | `formula` |
| "interactive exam", "parcial with answers", "exam with toggle", "parcial interactivo" | Interactive Exam with Toggle Answers **(Template 7)** | `{slug}-v{N}.html` | `exam` |

**Tag parameter**: Pass the suggested tag (max 7 lowercase letters) to `write_study_object` via the `tag` parameter. The model may choose any tag; the UI will assign a deterministic color.

---

## Design Notes Convention

Before coding, **read existing design notes** from `subjects/{subject}/references/` using `read_vault_file(path='references/object-{slug}-design.md')` or list files by attempting common slugs. Then write your design plan using `write_design_notes` (saves to `subjects/{subject}/references/`):

```markdown
## Design Plan: {type} — {subject}

### Content outline
- Topics to cover: ...
- Question count: ...
- Difficulty spread: ...

### Theme
- primary: {color}, secondary: {color}, accent: {color}
- Icon: {emoji}

### Template structure note
- Using {template} format
- Key structural decisions: ...

### Build prompt (self-instruction)
1. ...
2. ...
3. ...
```

This becomes a reference for future study sessions on the same subject.

## Reference Files

- **`references/multi-topic-exam-selection.md`** — methodology for selecting and designing exercises when building comprehensive multi-topic exams (coverage strategy, difficulty analysis, sub-question design, pitfalls). Load this when building any exam that spans 3+ topic areas.
