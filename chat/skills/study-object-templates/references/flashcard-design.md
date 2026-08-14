# Flashcard Design: Distractor Quality, Explanations, Difficulty

The flashcards template's data format is only half the story. This file is the quality bar that separates a quiz that trains understanding from a quiz that trains guessing. Read it before writing any QUESTIONS array.

## Distractor rules (the four wrong options)

The purpose of distractors is to force the student to actually know the concept. A distractor you can eliminate by style, length, or absurdity is a wasted question.

- **Every distractor must be plausible**: a realistic answer a student who half-remembers the topic would pick. If a distractor is clearly nonsense, replace it with a real misconception from the material.
- **Distractors must be mutually exclusive**: no two options can both be true, and none can be a subset of another. Overlapping options make the question ambiguous or answerable by elimination.
- **No "all of the above" / "todas las anteriores" / "ninguna de las anteriores"** — they reward test-taking, not knowledge, and interact badly with shuffled options.
- **Keep options parallel**: same grammatical structure, similar length, same level of specificity. A much longer correct option ("the real answer, the real answer, the real answer") is a giveaway.
- **Distractors should come from the material**: the best distractors are real concepts the student might confuse with the correct one (e.g. for a question about BCNF: "toda relación en 3FN está en BCNF" — the actual misconception). Steal these from the wiki pages; they are listed as common errors in the course material.
- **Numbers in calculation questions**: wrong options must be plausible computation errors (off by a factor, wrong units, inverted ratio) — not random numbers. State the error each distractor represents in your head as you write it (e.g. "olvidó multiplicar por 1/2").

## Explanation anatomy

The feedback shown after answering is where the learning happens. Write every explanation with two halves:

1. **Why the correct answer is correct** — the mechanism, not just the fact. Name the concept and the reasoning in 2-3 sentences.
2. **Why each key distractor is wrong** — explicitly address the plausible ones, ideally with the specific misconception they encode. If an option is wrong for the same reason as another, group them ("las demás opciones confunden X con Y").

The `detail` field then expands beyond the question: related concepts, the general rule the question illustrates, an extra example, or the edge case. It should stand alone even if the student skipped the question text — it's a mini-lesson.

## Difficulty spread

A good set is a ladder, not a wall. Aim for roughly **30% básica / 50% media / 20% alta** (for a 30-question set: ~9 / 15 / 6).

- **Baja**: definition recall, identifying a concept, one-step facts. Tests vocabulary.
- **Media**: applying a concept to a new situation, comparing two concepts, choosing the correct SQL/relational operation for a described need.
- **Alta**: multi-step reasoning, combining 2+ concepts, evaluating a statement (e.g. which claim about BCNF is correct), calculation, or "what happens if…" variations.

Label them with `diff` (e.g. `Baja` / `Media` / `Alta`; the engine renders them as colored badges). Keep the array ordered by difficulty — the engine preserves array order.

## Coverage

- Every major topic area from the wiki gets at least 2-3 questions (so the results screen shows a meaningful per-topic breakdown).
- Don't repeat the same concept twice in a row; interleave topics.
- Prefer questions that force discrimination between commonly-confused concepts (UNION vs UNION ALL, immediate vs deferred log, 3FN vs BCNF) — these are the highest-value cards.

## Self-check checklist (run before saving)

1. Every question: exactly 4 options, `correct` in [0..3], unique `id`, `tag` and `diff` present with matching color-map entries.
2. Copy the QUESTIONS array into a `.json` file — it must parse (no trailing commas, no unescaped quotes in strings).
3. No option contains "all of the above"-type phrases; no two options overlap in meaning.
4. No distractor is absurd on its face; each represents a plausible error.
5. Every explanation names why the correct option is correct AND why the distractors are wrong.
6. Difficulty spread is roughly 30/50/20.
7. Question text renders correctly with HTML (escape `'` inside strings, use `<code>` for inline code, `<div class="code-block">` for multi-line).
