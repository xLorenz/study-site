# Template 3: Interactive Flashcards / Quiz

## Purpose
Full interactive multiple-choice quiz with feedback, progress tracking, confetti on correct answers, keyboard navigation.

## Structure
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

## Data format
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

## State management
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

## CSS custom properties
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

## Hard mode differences
- Accent: `#fb923c` (orange) instead of `#a78bfa` (purple)
- Added `.badge-hard` element with "HARD MODE" label
- Header max-width: 700px (vs 640px)
- Content is harder/different questions but same data format

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Read SCHEMA.md for subject conventions
  - Read ALL wiki files to extract key concepts
  - Read subjects/{subject}/references/ for notes
  - Design 30-50 questions MAX (to avoid bloated HTML file)
  - Each question needs: {id, tag, tagLabel, question, options[4], correct, explanation, detail}
  - Cover all major topic areas from the wiki
  - Write ALL question content yourself

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
