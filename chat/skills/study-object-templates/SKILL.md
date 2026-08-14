---
name: study-object-templates
title: "Study Object Templates — HTML Generation Reference"
description: "Canonical reference for the 7 HTML template formats (static mock exam, solutions, interactive flashcards, mind maps, cheat sheets, formula decks, interactive exam with toggle answers). Used by study-professor when building interactive study aids."
---

# Study Object Templates

This skill describes **7 canonical HTML template formats**. The `study-professor` skill points here when generating study objects — **always load this skill** (`read_skill(skill_name='study-object-templates')`) before generating any new study object, then read the specific template file from `templates/` and any references it points to.

## Available Templates

| # | Template | File | Interactivity | Tag |
|---|----------|------|---------------|-----|
| 1 | Static Mock Exam | `templates/01-mock-exam.md` | None (static) | `mock` |
| 2 | Solutions Document | `templates/02-solutions.md` | None (static) | `solutions` |
| 3 | Interactive Flashcards | `templates/03-flashcards.md` | Full JS quiz | `flash` |
| 4 | Interactive Mind Map | `templates/04-mind-map.md` | Full JS (D3.js, radial tree) | `mindmap` |
| 5 | Interactive Cheat Sheet | `templates/05-cheat-sheet.md` | Full JS (filters, search, expand) | `cheat` |
| 6 | Formula Deck | `templates/06-formula-deck.md` | Full JS (cheat-sheet engine) | `formula` |
| 7 | Interactive Exam (Toggle Answers) | `templates/07-interactive-exam.md` | Minimal JS show/hide | `exam` |

To load a template: `read_skill(skill_name='study-object-templates', path='templates/01-mock-exam.md')`

## Bundled Assets (canonical boilerplate — copy, never rewrite)

Templates 3, 4, 5 and 7 ship their interactive engine as canonical files in `assets/`. Copy them verbatim into the generated HTML and fill in only the data consts at the top (QUESTIONS, DATA, CARDS, etc.) — do not modify the engine functions. This guarantees production-tested behavior every run:

| Asset | Used by | Read via |
|-------|---------|----------|
| `assets/flashcards.js` — quiz engine (shuffle, feedback, confetti, keyboard, sequential navigation with Next disabled until answered, results) | Template 3 | `read_skill(skill_name='study-object-templates', path='assets/flashcards.js')` |
| `assets/flashcards.css` — quiz styles | Template 3 | same, `path='assets/flashcards.css'` |
| `assets/mindmap.js` — D3 radial tree engine (fixed positions, straight tinted links, SVG rings, zoom/pan, search by name+desc, detail panel, tooltip, scoped staggered entrance + all-node subtle glow, expand/collapse, instant whole-map ops, no double-click zoom) | Template 4 | same, `path='assets/mindmap.js'` |
| `assets/mindmap.css` — mind map styles | Template 4 | same, `path='assets/mindmap.css'` |
| `assets/cheat-sheet.js` — cheat sheet engine (topic filters, formulas-only toggle, search, fixed-column cascade card expansion via clickable headers, multi-CDN KaTeX with unicode fallback) | Templates 5 and 6 | same, `path='assets/cheat-sheet.js'` |
| `assets/cheat-sheet.css` — cheat sheet styles | Templates 5 and 6 | same, `path='assets/cheat-sheet.css'` |
| `assets/interactive-exam.js` — answer toggle handler | Template 7 | same, `path='assets/interactive-exam.js'` |

---

## Common Build Flow (ALL templates — do this before coding)

Every study object starts with the same three reads, then a design note. Do not skip to coding until the design is written down.

1. **Read SCHEMA.md**: `read_vault_file(path='SCHEMA.md')` — subject conventions and language rules
2. **Read the content**: ALL `.md` files in `subjects/{subject}/wiki/` (batch reads, max 10 per turn) plus any raw practice files the template asks for
3. **Read prior context**: `subjects/{subject}/references/` — previous design notes and session notes
4. **Check for an existing design note**: `read_vault_file(path='references/object-{slug}-design.md')`
5. **Write a design plan** via `write_design_notes` (`references/object-{slug}-design.md`): content outline, theme, template choice, and a self-instruction build prompt. This becomes the reference for future sessions on the same subject. (Template: the Design Notes Convention section below.)

Templates' STEP 1 sections build on this flow with their format-specific content rules.

## Common Patterns (ALL templates)

### Theme sourcing
Read the subject's theme file — `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — **always read it first**. The Subject Theme section in the system prompt is only a fallback if the file is missing. Set the template's `:root` theme vars (primary/secondary/accent) from it; never hardcode fixed defaults.

### Color scheme
- Background: `#0a0a0f` to `#0f0f13` — very dark
- Text: `#e2e2e8`, secondary `#6a6a7a` / `#b0b0c0`
- Surfaces: `#111118`, `#18181c`, `#1f1f2a`
- Borders: `#1e1e2a`, hover `#2a2a3a`
- Accent varies by subject/theme (see Theme sourcing above)

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
.fn   { color: #dcdcaa; } /* function names */
```

### Code block pattern
```html
<div class="code"><pre>
<span class="kw">public</span> <span class="type">String</span> foo() { ... }
</pre></div>
```

### Responsive
- `@media (max-width: 480px)` or `@media (max-width: 640px)` breakpoints
- Font-size reduction, padding adjustments
- No fixed pixel widths for layout (container `max-width` only)

### Print
- `@media print` hides interactive elements, inverts backgrounds to white
- Code blocks get light gray background
- Interactive formats print their content expanded: template 7 must show all answers (rule in the template); flashcards print only correct options

### Accessibility (interactive templates)
- `:focus-visible` outline on all interactive elements (options, buttons, controls)
- Feedback regions announce via `role="status"` / `aria-live="polite"` (built into assets/flashcards.js)
- `@media (prefers-reduced-motion: reduce)` disables animations/transitions (built into the CSS assets)
- Keyboard: every interaction has a keyboard path — arrows/1-4 in flashcards, `/`+Escape in mind map, buttons are focusable everywhere

---

## Template Selection Guide

When the user asks for a study object, pick by type keyword:

| User says | Template | Tag suggestion |
|-----------|----------|----------------|
| "mock exam", "parcial", "practice exam" | Template 1 — Static Mock Exam | `mock` |
| "solutions", "answer key", "solucionario" | Template 2 — Solutions Document | `solutions` |
| "flashcards", "flash", "quiz", "mcq" | Template 3 — Interactive Flashcards | `flash` |
| "mind map", "mapa conceptual", "concept map" | Template 4 — Interactive Mind Map | `mindmap` |
| "cheat sheet", "reference card", "resumen" | Template 5 — Interactive Cheat Sheet | `cheat` |
| "formula deck", "formulas" | Template 6 — Formula Deck (cheat-sheet engine, all `kind:'formula'` cards) | `formula` |
| "interactive exam", "parcial with answers", "exam with toggle" | Template 7 — Interactive Exam (Toggle Answers) | `exam` |

**Tag parameter**: Pass the suggested tag (max 7 lowercase letters) to `write_study_object` via the `tag` parameter. The UI assigns a deterministic color from the tag string.

---

## Design Notes Convention

Before coding, **read existing design notes** from `subjects/{subject}/references/` using `read_vault_file(path='references/object-{slug}-design.md')`. Then write your design plan using `write_design_notes`:

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
- **`references/flashcard-design.md`** — distractor quality rules, explanation anatomy (why-correct + why-each-distractor-wrong), difficulty spread, coverage, and the self-check checklist. Load when building flashcards (template 3).
- **`references/formula-deck-verification.md`** — the four card parts, dimensional analysis, numeric sanity checks, cross-checking with the wiki, common failure patterns (missing constants, inverted ratios, validity conditions). Load when building formula decks (template 6).
- **`references/cheat-sheet-selection.md`** — what belongs on a cheat sheet (frequent use, high mistake rate, high-density facts) and what stays out, card anatomy, grouping rules. Load when building cheat sheets (template 5).