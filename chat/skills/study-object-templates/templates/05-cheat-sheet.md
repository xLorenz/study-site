# Template 5: Cheat Sheet

## Purpose
Compact, scannable reference card with key concepts, syntax snippets, and quick reminders. Optimized for rapid lookup during coding or study — not a narrative document. No JS interaction.

## Structure
```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono)
│   ├── <style> — dark theme, compact cards, two-column optional layout
│   └── </head>
├── <body>
│   ├── <div class="container">
│   │   ├── <h1> — gradient title
│   │   ├── <p class="subtitle"> — brief description
│   │   ├── <div class="toc"> — optional anchor links to sections
│   │   ├── <div class="section">  ← repeat per topic
│   │   │   ├── <h2> topic title
│   │   │   ├── <div class="ref-card">  ← repeat per concept
│   │   │   │   ├── <h3> concept name <span class="badge">tag</span>
│   │   │   │   ├── <p> brief explanation (1-2 sentences)
│   │   │   │   ├── <div class="code"><pre> syntax example </pre></div>
│   │   │   │   └── <p class="note"> tip, edge case, or common pitfall
│   │   │   └── </div>
│   │   └── </div>
│   │   └── <div class="footer">
│   └── </body>
```

## CSS details
- `.ref-card`: compact card, `padding: 0.75rem 1rem`, smaller than exam sections
- `.ref-card h3`: inline with `.badge` floated right
- `.note`: italic, secondary text color (`#6a6a7a`), small font
- Optional grid: `.section` can use `display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;` for dense topics
- Same dark theme variables, syntax highlighting, responsive/print as common patterns
- Container max-width: 1100px (wider to accommodate two-column layout)
- No `.question`, `.alert`, or `.qa` — this is not an exam, it's a reference

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Read SCHEMA.md for subject conventions
  - Read ALL wiki files
  - Read subjects/{subject}/references/ for notes
  - Identify 15-30 key concepts/syntax patterns to cover
  - Each entry: concept name, 1-2 sentence explanation, code example, usage tip
  - Group into logical topic sections (e.g. "Data Types", "Control Flow", "Collections")
  - Focus on most-used patterns and common mistakes

STEP 2 — THEME LOOKUP
  - Read `references/_theme.md` or use system prompt theme colors
  - Title gradient = linear-gradient(135deg, primary, secondary)
  - Section h2 uses secondary/accent color
  - Code blocks use standard syntax highlighting

STEP 3 — HTML STRUCTURE
  - Write self-contained HTML with all CSS inline
  - Optional .toc at top with anchor links to each section
  - One .section per topic group
  - For very dense subjects, use two-column grid layout
  - Code snippets in .code > pre with syntax spans
  - Keep it scannable: short explanations, generous use of .note for tips

STEP 4 — SAVE & LOG
  - Call `write_study_object` with filename, tag="cheat", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```
