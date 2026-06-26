---
name: study-object-templates
title: "Study Object Templates — HTML Generation Reference"
description: "Canonical reference for the 7 HTML template formats (static mock exam, solutions, interactive flashcards, mind maps, cheat sheets, formula decks, interactive exam with toggle answers). Used by study-professor when building interactive study aids."
---

# Study Object Templates

This skill describes **7 canonical HTML template formats**. The `study-professor` skill points here when generating study objects — **always load this skill** (`skill_view(name='study-object-templates')`) before generating any new study object, then read the specific template file from `templates/`.

## Available Templates

| # | Template | File | Interactivity | Tag |
|---|----------|------|---------------|-----|
| 1 | Static Mock Exam | `templates/01-mock-exam.md` | None (static) | `mock` |
| 2 | Solutions Document | `templates/02-solutions.md` | None (static) | `solutions` |
| 3 | Interactive Flashcards | `templates/03-flashcards.md` | Full JS quiz | `flash` |
| 4 | Interactive Mind Map | `templates/04-mind-map.md` | Full JS (D3.js) | `mindmap` |
| 5 | Cheat Sheet | `templates/05-cheat-sheet.md` | None (static) | `cheat` |
| 6 | Formula Deck | `templates/06-formula-deck.md` | None (static) | `formula` |
| 7 | Interactive Exam (Toggle Answers) | `templates/07-interactive-exam.md` | Minimal JS show/hide | `exam` |

To load a template: `skill_view(name='study-object-templates', path='templates/01-mock-exam.md')`

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

---

## Template Selection Guide

When the user asks for a study object, pick by type keyword:

| User says | Template | Tag suggestion |
|-----------|----------|----------------|
| "mock exam", "parcial", "practice exam" | Template 1 — Static Mock Exam | `mock` |
| "solutions", "answer key", "solucionario" | Template 2 — Solutions Document | `solutions` |
| "flashcards", "flash", "quiz", "mcq" | Template 3 — Interactive Flashcards | `flash` |
| "mind map", "mapa conceptual", "concept map" | Template 4 — Interactive Mind Map | `mindmap` |
| "cheat sheet", "reference card", "resumen" | Template 5 — Cheat Sheet | `cheat` |
| "formula deck", "formulas" | Template 6 — Formula Deck | `formula` |
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
