# Template 3: Interactive Flashcards / Quiz

## Purpose
Full interactive multiple-choice quiz with feedback, progress tracking, confetti on correct answers, keyboard navigation.

## Canonical boilerplate (copy, don't rewrite)

The JS engine and CSS are canonical, production-tested files — **copy them verbatim** into the generated HTML:

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/flashcards.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` (primary/secondary/accent/header-fg) come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/flashcards.js')` → paste into `<script>`. **Fill in ONLY** the three consts at the top: `QUESTIONS`, `TOPIC_COLORS`, `DIFF_COLORS`. Do not modify the engine functions.

This guarantees correct behavior every time (shuffle, progress, confetti, keyboard, results). The full HTML skeleton is:

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> — flashcards.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   ├── .sub — metadata line
│   │   ├── .stats (✅ <span id="statOk">, ❌ <span id="statBad">, 📊 <span id="statTotal">)
│   │   └── .progress-wrap > .progress-fill#progressFill
│   ├── <div class="wrap">
│   │   ├── <main id="cardArea">
│   │   └── .hint (keyboard shortcuts, <kbd> tags)
│   ├── .bottom-bar (btnPrev, counter, btnNext, btnReset)
│   ├── <canvas id="confetti">
│   └── <script> — flashcards.js
```

Element IDs are fixed — the engine looks them up by id (`cardArea`, `statOk`, `statBad`, `statTotal`, `progressFill`, `counter`, `btnPrev`, `btnNext`, `btnReset`, `confetti`). Keep them exact.

## Data format

```javascript
const QUESTIONS = [
  {
    id: 'q1',
    tag: 'fundamentos',      // category key — must exist in TOPIC_COLORS
    tagLabel: 'Fundamentos',  // display label
    diff: 'Media',            // difficulty label — must exist in DIFF_COLORS
    question: 'HTML question text with <code>inline code</code> or <div class="code-block">...</div>',
    options: ['Option A', 'Option B', 'Option C', 'Option D'],
    correct: 2,               // index of correct option (0-based)
    explanation: 'HTML explanation shown after answering',
    detail: 'Extra detail shown below explanation'
  }
]
```

```javascript
const TOPIC_COLORS = {
  fundamentos: '#a78bfa',   // one entry per tag used in QUESTIONS
};
const DIFF_COLORS = { 'Baja':'#4ade80', 'Media':'#fbbf24', 'Alta':'#fb923c' };
```

## Hard mode differences
- Accent: orange (`#fb923c`) instead of the theme accent
- Added `.badge-hard` element with "HARD MODE" label
- Header max-width: 700px (vs 640px)
- Content is harder/different questions but same data format

## Behavior notes (engine-enforced, do not override)
- Navigation is strictly sequential: **Next advances to the next card and is DISABLED until the current card is answered** — a question can never be skipped. The disabled state is enforced in `nextCard` (guard `!(idx in state.answers)`) and on the button (`btnNext').disabled = !currentAnswered`), and `btnReset` re-enables everything.
- Keyboard: 1-4 answer, ←/→ prev/next, R reset; Enter advances after answering.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md (SCHEMA.md → wiki → references → design notes)
  - Read references/flashcard-design.md — distractor quality rules, explanation
    anatomy, difficulty spread, and the self-check checklist. Apply them all.
  - Design 30-50 questions MAX (to avoid bloated HTML file)
  - Each question needs: {id, tag, tagLabel, diff, question, options[4], correct, explanation, detail}
  - Cover all major topic areas from the wiki
  - Write ALL question content yourself

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first; the system prompt's Subject Theme section is only a fallback if the file is missing
  - Set the `← theme` vars in the copied CSS; pick TOPIC_COLORS hues from the theme

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/flashcards.css into <style>, set the theme vars
  - Copy assets/flashcards.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in QUESTIONS, TOPIC_COLORS, DIFF_COLORS with your designed content

STEP 4 — SELF-CHECK (each item must pass)
  - Every question has exactly 4 options and correct in [0..3]
  - Every id is unique; every tag has a TOPIC_COLORS entry; every diff has a DIFF_COLORS entry
  - The QUESTIONS array parses as valid JSON when copied to a .json file (no trailing commas, no unescaped quotes)
  - No option contains "todas las anteriores" / "all of the above" / "ninguna de las anteriores"
  - Options don't overlap each other in meaning; distractors are plausible but unambiguously wrong

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag, and full HTML
  - Pass `tag` parameter (e.g. "flash")
  - Log to subjects/{subject}/wiki/log.md
```
