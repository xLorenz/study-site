# Template 6: Formula Deck

## Purpose
Quick-reference formula cards showing formula, description, variable definitions, and usage notes. Print-friendly, no JS. Ideal for math, physics, statistics, and computational complexity.

## Structure
```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono)
│   ├── <style> — dark theme, formula cards, accent borders
│   └── </head>
├── <body>
│   ├── <div class="container">
│   │   ├── <h1> — gradient title
│   │   ├── <p class="subtitle"> — topic + formula count
│   │   ├── <div class="section">  ← repeat per topic group
│   │   │   ├── <h2> topic title
│   │   │   ├── <div class="formula-card">  ← repeat per formula
│   │   │   │   ├── <div class="formula-desc"> formula name / what it computes
│   │   │   │   ├── <div class="formula"> the formula (monospace, accent color)
│   │   │   │   ├── <table class="formula-vars"> variable definitions
│   │   │   │   │   ├── <tr><td class="var">x</td><td>description</td></tr>
│   │   │   │   │   └── ...
│   │   │   │   └── <div class="formula-note"> usage hint / unit / edge case
│   │   │   └── </div>
│   │   └── </div>
│   │   └── <div class="footer">
│   └── </body>
```

## CSS details
- `.formula-card`: card with `border-left: 4px solid var(--accent)`, subtle glow
- `.formula`: monospace (`JetBrains Mono`), `font-size: 1.3rem`, accent color (`#4fc1ff` or theme accent)
- `.formula-vars`: two-column table, `.var` column monospace and gold, descriptions in secondary text
- `.formula-desc`: bold title text
- `.formula-note`: italic, secondary text, small
- Same dark theme, responsive, and print patterns as other templates
- Container max-width: 900px
- `.section` uses same card style as mock exam

## Formula display patterns
- Use `<span class="f-sym">` for symbols (italic), `<span class="f-op">` for operators, `<span class="f-num">` for numbers
- Alternatively, use `.code > pre` for multi-line or complex formulas
- For physics: include units in `.formula-note` or as a third column

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Read SCHEMA.md for subject conventions
  - Read ALL wiki files and raw practice files for formula references
  - Read subjects/{subject}/references/ for existing notes
  - Collect all key formulas (15-30 depending on subject breadth)
  - Each formula needs: name, formula expression, variable definitions (name + description), usage note
  - Group into logical topic sections

STEP 2 — THEME LOOKUP
  - Read `references/_theme.md` or use system prompt theme colors
  - Formula text color uses accent
  - Variable names in gold
  - Border-left accent per formula card

STEP 3 — HTML STRUCTURE
  - Write self-contained HTML with all CSS inline
  - One .section per topic group
  - Each formula in .formula-card with desc, formula, vars table, note
  - For mathematical formulas, use styled spans or pre blocks
  - Keep units and edge cases visible in .formula-note

STEP 4 — SAVE & LOG
  - Call `write_study_object` with filename, tag="formula", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```
