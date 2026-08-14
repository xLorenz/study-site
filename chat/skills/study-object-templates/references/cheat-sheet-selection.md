# Cheat Sheet Selection: What Goes In, What Stays Out

A cheat sheet is a compression problem: the student needs maximum retrieval per square centimeter. This file defines what deserves a card, how to group cards, and how to keep the sheet scannable. Read it before writing any cheat sheet.

## What belongs on a cheat sheet

A cheat sheet is NOT a summary of the wiki. It's a **lookup index for the things that are easy to forget or hard to get right under time pressure**. Select for:

1. **Frequent use** — syntax and patterns the student reaches for constantly (how to write a GROUP BY, how to declare an array, the sign of the work done by a force).
2. **High mistake rate** — the classic pitfalls the material calls out: WHERE vs HAVING, UNIQUE vs PRIMARY KEY, break vs continue, 3FN vs BCNF, immediate vs deferred log. The wiki pages that list "errores comunes" are gold — every one of those errors gets a card with the correction.
3. **Compact, high-density facts** — tables that summarize (normal forms, ACID properties, conversion formulas, operator precedence) where a card replaces a page of notes.
4. **Quick reminders of exact syntax** — one small code block beats three sentences of prose every time.

## What stays out

- **Narrative explanations** — a cheat sheet is not for understanding; it's for retrieval. If a concept needs more than 2 sentences to explain, it belongs in the wiki, not here. (The design notes and wiki are the narrative; the cheat sheet is the index.)
- **Obvious facts the student already knows** — "a variable stores a value" type content. If a card could be written from common sense, cut it.
- **Everything from the wiki** — 15-30 cards, not one per page. The point is ruthless selection.
- **Long examples** — a card is one pattern, not a tutorial.

## Card anatomy

Each card: **title** (the search term the student thinks of), **summary** (1-2 sentence explanation), and a **detail** block that opens on click with the explanation, validity conditions, and the pitfall note. The pitfall is often the most valuable line on the card — make it specific ("sin WHERE, UPDATE afecta a TODAS las tuplas" beats "ten cuidado al usar UPDATE").

**Theorems, formulas, equations and constants get their own marker.** Every card belongs to its topic (cat), and if it is a theorem/formula/equation/constant it is ALSO tagged `kind: 'formula'` — it appears under its topic AND under the cross-topic "Solo fórmulas" toggle.

## Grouping and layout

- Group into **3-6 topic categories** (e.g. "Data Types", "Control Flow", "Collections"; "Normalización", "SQL", "Transacciones") — the student scans the category, not the sheet.
- 2-3 cards per topic minimum, 4-8 typical: a topic that needs 10+ cards is probably two topics.
- Cards are color-coded by topic (TOPIC_COLORS); the filter bar buttons let the student show only one topic at a time.
- Order cards within a topic by importance to the course, not alphabetically. The first cards are what the student will look at most.
- Cards expand independently — opening one must never resize the others: the engine renders **fixed columns** (`.cc-col` divs, `--cols`), so an open card only pushes the cards below it in its own column; columns never rebalance and the rest of the sheet stays put. Never restyle the grid as CSS `columns` (rebalancing) or a row-based grid (rows move together).
- Math symbols in formulas: write the LaTeX form in `$$…$$` followed by the unicode version (`'$$F = q(E + v \\times B)$$  F = q(E + v×B)'`). KaTeX is fetched from three CDNs in order (jsdelivr → unpkg → cdnjs); if all are unreachable the engine deletes the `$$…$$` blocks and shows the unicode — the card must stay readable, and raw `\frac` must never be visible.

## Self-check checklist (run before saving)

1. Every card answers one of: frequently used, commonly mistaken, high-density fact, exact-syntax reminder.
2. No card summary is longer than 2 sentences; the detail block holds the depth.
3. Every theorem/formula/equation/constant card has `kind: 'formula'` with a `$$…$$` + unicode formula field.
4. Every common pitfall from the wiki's "errores comunes" material has a card.
5. The sheet is scannable in under 10 seconds: clear topic labels, consistent card anatomy, colors per topic.
6. 15-30 cards total; no narrative paragraphs anywhere.