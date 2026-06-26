# Template 1: Static Mock Exam

## Purpose
Print-friendly static exam with theory questions and coding exercises. No JS interaction — just present the content.

## Structure
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

## CSS details
- `.section` card: `background: #18181c; border: 1px solid #27272a; border-radius: 12px; padding: 1.5rem;`
- `.question` block: `border-left: 3px solid #3b3b45; padding-left: 0.75rem;`
- `.alert` box: themed background with accent border, for hints/comments
- `.badge`: small rounded pill for point values
- Title: gradient `linear-gradient(135deg, accent1, accent2)` with `-webkit-background-clip: text; -webkit-text-fill-color: transparent`

## Build steps

```
STEP 1 — SCHEMA & CONTENT DESIGN
  - Read subjects/{subject}/SCHEMA.md for conventions
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
  - CSS: all common patterns (dark theme, code highlighting, responsive, print)
  - Container max-width: 900px
  - One .section per themed block
  - Each question in .question with .num for numbering
  - Code in .code > pre with syntax highlighting spans
  - Alerts in .alert for side-notes

STEP 4 — SAVE & LOG
  - Call `write_study_object` with filename, tag, and full HTML
  - Pass `tag` parameter (e.g. "mock")
  - Log to subjects/{subject}/wiki/log.md
```
