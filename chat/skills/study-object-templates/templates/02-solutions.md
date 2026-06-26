# Template 2: Solutions Document

## Purpose
Comprehensive answer key with navigation, Q&A pairs, cross-references.

## Structure
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

## Unique features
- `.nav` with anchor links to section IDs — navigation bar at top
- `.qa` pair pattern: `.q` gold (`#fbbf24`), `.a` green (`#bef264`)
- Can include `h4` sub-headers within sections
- Tags: `.tag.purple`, `.tag.blue`, `.tag.green`, `.tag.orange`, `.tag.red`, `.tag.pink`, `.tag.teal`
- Print-friendly: explicit `@media print` color overrides

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Read SCHEMA.md for subject conventions
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
