# Template 7: Interactive Exam with Toggle Answers

## Purpose
Long-form comprehensive multi-topic exam with per-exercise show/hide answer buttons. Each exercise includes sub-questions and a detailed step-by-step solution hidden behind a toggle. Dark theme, interactive answer revealers.

## Structure
```
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
│   │   │   │   ├── <div class="exercise-number"> — Exercise N — Topic Name
│   │   │   │   └── <div class="exercise-topics">
│   │   │   │       └── <span class="topic-tag.{type}"> — colored pill badges
│   │   │   ├── <div class="exercise-body">
│   │   │   │   ├── <p> problem statement
│   │   │   │   ├── <div class="data"> — data block (gold highlights)
│   │   │   │   ├── <div class="sub-question">  ← repeat per sub-question
│   │   │   │   │   └── <strong>a)</strong> question text
│   │   │   │   ├── <button class="btn-answer"> — toggle button
│   │   │   │   └── <div class="answer-box" id="ansN">
│   │   │   │       ├── <h4>SOLUTION
│   │   │   │       ├── <div class="step"> — one per sub-question
│   │   │   │       │   ├── <strong>step label</strong>
│   │   │   │       │   └── <div class="result"> — final result (accent color)
│   │   │   │       └── </div>
│   │   │   └── </div>
│   │   └── </div>
│   │   └── <div class="footer">
│   └── </body>
├── <script>
│   └── function toggleAnswer(id) { ... }
└── </html>
```

## CSS framework

Use the shared palette from the SKILL.md **Common Patterns** section (backgrounds, text, borders, surfaces). Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` and set `--primary`, `--secondary`, `--accent` from it (primary/secondary/accent) — do not hardcode fixed defaults; the system prompt's Subject Theme section is only a fallback if the file is missing. Template-specific additions only:
```css
:root {
  --gold: #fbbf24; --green: #4ade80; --red: #f87171; --orange: #fb923c;
  --radius: 12px; --radius-sm: 8px;
}
```

## Key class patterns

- **`.exercise`**: card with `border-radius: var(--radius)` and `overflow: hidden`
- **`.exercise-header`**: `background: var(--surface2)`, contains number + topic tags
- **`.exercise-body`**: `padding: 1.5rem` — holds statements, data, sub-questions
- **`.data`**: `background: var(--surface2)`, gold `strong` for numerical data
- **`.formula-box`**: `border-left: 3px solid var(--primary)`, monospace
- **`.sub-question`**: `border-left: 2px solid var(--border)`, `padding-left: 1.2rem`
- **`.btn-answer`**: toggle button with show/hide state; `.showing` class when visible (green border)
- **`.answer-box`**: hidden by default (`display: none`), visible with `.visible` class (`display: block` + fadeIn)
- **`.answer-box .step`**: individual sub-question resolution, separated by `border-bottom`
- **`.answer-box .result`**: final answer in `JetBrains Mono` with accent green color

## Topic tags (pill badges)

Use subject-appropriate topic colors derived from the theme. Example pattern:
```css
.topic-tag.theme-a { border-color: #4fc1ff44; color: #4fc1ff; }
.topic-tag.theme-b { border-color: #a78bfa44; color: #a78bfa; }
```

## Toggle answer JavaScript (canonical — copy verbatim)

Copy `read_skill(skill_name='study-object-templates', path='assets/interactive-exam.js')` into a `<script>` tag at the bottom. It's the same three-line handler as below — don't rewrite it:

```javascript
function toggleAnswer(id) {
  const box = document.getElementById(id);
  const btn = box.previousElementSibling;
  box.classList.toggle('visible');
  btn.classList.toggle('showing');
  btn.textContent = box.classList.contains('visible')
    ? 'Hide answer'
    : 'Show answer';
}
```

No dependencies, no state management, no confetti. Each exercise has its own independent toggle.

## Print behavior (required)

`@media print` must force all answers visible — a printed exam with hidden answers is useless:

```css
@media print {
  .btn-answer { display: none; }
  .answer-box { display: block !important; }
}
```

Both production exams use this pattern; keep it in every interactive exam.

## Content design rules

1. **Select the hardest/comprehensive exercises** from each topic area
2. **Cover ALL requested topics** — don't skip any
3. **Each exercise ≈ 4-5 sub-questions** building from basic to synthesis
4. **Include a `data` block** with all constants at the top of each exercise
5. **Answers must be step-by-step** with the final result highlighted in `.result` blocks
6. **No topics outside the requested set**
7. **Exercises should be multi-topic where natural**

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md (SCHEMA.md → wiki → references → design notes)
  - Read ALL raw practice files from subjects/{subject}/raw/ (practice files, not just wiki summaries — the specific exercises and numbers matter here)
  - For each requested topic, identify the 1-2 hardest problems in that practice file
  - Look for exercises that combine multiple concepts
  - Design 1 exercise per topic cluster
  - Each exercise: 4-5 sub-questions (a, b, c, d, e) building in complexity
  - Each exercise: include a <div class="data"> block with all given constants
  - Each sub-question: write a complete step-by-step solution in advance

STEP 2 — THEME & HTML
  - Follow the CSS framework (dark theme, exercise cards, toggle buttons)
  - Use topic tag pills matching the subject's topic areas
  - Container max-width: 960px

STEP 3 — ANSWER TOGGLES
  - Each exercise gets a unique answer box id: ans1, ans2, etc.
  - Each answer box is a sibling of the toggle button
  - Answers use .step per sub-question, .result for final results
  - Copy the canonical toggle function from assets/interactive-exam.js into a <script> tag at the bottom
  - Include the required @media print rule that expands all answers

STEP 4 — SELF-CHECK
  - Every exercise has exactly one btn-answer + one answer-box, ids unique
  - Each solution is step-by-step with the final result in a .result block
  - Every sub-question (a, b, c, d) has a matching .step — no sub-question left unsolved
  - Verify the math with an independent method where possible (alternate formula, unit check, sanity check of magnitudes)

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="exam", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```
