# Template 13: True/False Rapid Round

## Purpose
Timed true/false sprint with a difficulty picker: the student chooses seconds-per-question up front, then answers statements that ramp from easy to hard (Dificultad 1 → 2 → 3). Instant feedback with explanation, low-time warning, and a results screen with topics, total time and a "para repasar" list of the missed statements. Best for myth-busting and rapid coverage of many small facts.

## Canonical boilerplate (copy, don't rewrite)

1. **CSS**: `read_skill(skill_name='study-object-templates', path='assets/tf.css')` → paste into `<style>`. Only the `:root` vars marked `← theme` come from the subject theme.
2. **JS engine**: `read_skill(skill_name='study-object-templates', path='assets/tf.js')` → paste into `<script>`. **Fill in ONLY** the `STATEMENTS`, `TOPIC_COLORS` and optionally `DEFAULT_SECONDS` consts. The difficulty picker (`DIFFICULTIES`) is FIXED in the engine — do not modify it. Do not modify the engine functions.

HTML skeleton with the fixed element IDs the engine looks up:

```
├── <head>
│   ├── Google Fonts (Inter + JetBrains Mono via <link>)
│   ├── <style> — tf.css + theme :root vars
│   └── </head>
├── <body>
│   ├── <header>
│   │   ├── <h1> title
│   │   ├── .sub — metadata line
│   │   └── .stats (⭐ <span id="tfScore">, .stat.progress-stat <span id="tfProgress">)
│   ├── <div class="wrap">
│   │   ├── <div id="tfIntro">
│   │   │   ├── <h2>Elige la dificultad</h2>
│   │   │   ├── .intro-sub (explains the ramp: 1 → 3, 1-4 keys)
│   │   │   ├── <div id="tfDiffButtons"></div>  (filled by engine)
│   │   │   └── .intro-keys (keyboard hints)
│   │   ├── <div id="tfCard" class="hidden">
│   │   │   ├── .timer-wrap (.timer-top > <span id="tfTimerText">, .timer-track > <div id="tfTimerBar">)
│   │   │   ├── <div id="tfStatement"></div>
│   │   │   ├── .tf-answers (#tfTrue "Verdadero", #tfFalse "Falso")
│   │   │   ├── <div id="tfFeedback" class="tf-feedback hidden">
│   │   │   └── <button id="tfNext" class="hidden">Siguiente</button>
│   │   └── <div id="tfResults" class="hidden">
│   │       ├── <div id="tfSummary">
│   │       └── <div id="tfMissedList" class="hidden">
│   ├── .bottom-bar (#tfRestart "Otra ronda" + #tfChangeDiff "Cambiar dificultad")
│   └── <script> — tf.js
```

## Data format

```javascript
const STATEMENTS = [
  { id:'t1', topic:'cinematica', topicLabel:'Cinemática',
    statement:'<b>En el MRU la aceleración es nula.</b>',
    answer:true, diff:1,
    explanation:'<p>El MRU tiene velocidad constante, por lo tanto $$a = dv/dt = 0$$ a = 0.</p>' },
  { id:'t2', topic:'dinamica', topicLabel:'Dinámica',
    statement:'<b>Masa y peso son lo mismo.</b>',
    answer:false, diff:3,
    explanation:'<p>La masa es intrínseca; el peso depende de la gravedad.</p>' }
];
const TOPIC_COLORS = { cinematica:'#5b7fc4', dinamica:'#fbbf24' };
const DEFAULT_SECONDS = 20;
```

- `answer` is a boolean; `explanation` is required HTML (shown after every answer, right or wrong); math uses `$$LaTeX$$ fallback-text`.
- `diff` is 1 (fácil), 2 (media) or 3 (difícil). **The engine always runs Dificultad 1 → 2 → 3**, shuffled within each difficulty — the round gets harder as it progresses. Aim for a third of the statements per difficulty.
- 10–24 statements. Mix of true and false (roughly balanced); false statements are plausible misconceptions from the wiki. Every topic key must exist in `TOPIC_COLORS` (max 4 topics).

## Behavior notes (engine-enforced, do not override)

- The round does NOT start on load: the intro screen's picker sets seconds per question (Relajado 30s / Normal 20s / Reto 10s / Experto 6s — Normal uses `DEFAULT_SECONDS`).
- Answering FREEZES the timer bar where it is; the seconds count stops. Under 6 s left, the count and the bar turn red and pulse.
- Timeout counts as wrong and reveals the correct answer. Feedback shows before "Siguiente"; no going back.
- Results: score circle, total elapsed time, per-topic accuracy bars, and a "Para repasar" list of every missed/timed-out statement tagged with its topic color.
- Keyboard: 1-4 pick difficulty on the intro, T/F answer, **← / → arrows answer too (← Verdadero, → Falso)**, Enter next.
- Exactly ONE keyboard-hint line shows at a time: the intro shows its static `.intro-keys`, and once the round starts the engine injects a `.tf-keys-hint` line into the card (and hides any generic `.hint` on the page to avoid duplication).
- Print: the intro and controls hide; the results screen prints.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md
  - Mine the wiki for facts with a clear true/false reading and common misconceptions
  - Assign diff 1/2/3 so the round ramps: easy recall first, tricky edge cases last
  - Every statement must be unambiguously TRUE or FALSE (no "depends")
  - explanation always explains WHY, referencing the wiki concept
  - Write ALL content yourself

STEP 2 — THEME
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` — always read it first
  - Set the `← theme` vars in the copied CSS; pick TOPIC_COLORS hues from the theme

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/tf.css into <style>, set the theme vars
  - Copy assets/tf.js into <script> verbatim
  - Build the skeleton with the fixed element IDs
  - Fill in STATEMENTS, TOPIC_COLORS (DEFAULT_SECONDS optional)

STEP 4 — SELF-CHECK (each item must pass)
  - Every id unique; every topic key has a TOPIC_COLORS entry
  - Roughly balanced true/false; a third of statements per difficulty 1/2/3
  - Every statement has an explanation that explains the correct answer
  - Every formula follows `$$LaTeX$$ fallback-text`
  - The STATEMENTS array parses as valid JSON when copied to a .json file

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="tf", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```