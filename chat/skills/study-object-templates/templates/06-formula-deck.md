# Template 6: Formula Deck

## Purpose
Interactive formula cards built with the **cheat-sheet engine** (assets/cheat-sheet.js + .css). Every theorem / formula / equation / constant is a card with `kind: 'formula'`, so it appears color-coded under its topic AND under the formulas-only toggle. Cards show the formula, a variables table, a numeric/dimensional verification, and a usage note. KaTeX renders the math when available; unicode fallback always works.

This template reuses the interactive cheat sheet's canonical engine — **do not write a separate formula-deck engine**. The only difference from Template 5 is content: all cards are formulas.

## Build steps

```
STEP 1 — CONTENT DESIGN
  - Follow the Common Build Flow in SKILL.md (SCHEMA.md → wiki → references → design notes)
  - Read references/formula-deck-verification.md — the four card parts, dimensional analysis,
    numeric sanity checks, cross-check with the wiki, common failure patterns
    (missing 4πε₀/μ₀ factors, inverted ratios, validity conditions)
  - Read references/cheat-sheet-selection.md — card anatomy and grouping rules
  - Collect all key formulas (15-30 depending on subject breadth); group into 3-6 topic categories
  - Each formula card needs:
      title, summary (what it computes, 1 sentence),
      formula in $$…$$ LaTeX + unicode fallback,
      detail with: variables table (name + unit), verification (numeric example or
      dimensional check), usage note (validity conditions, traps, sign conventions)
  - Verify every formula: units consistent, one numeric example per topic group,
    symbol-for-symbol match with the wiki

STEP 2 — THEME LOOKUP
  - Read `subjects/{subject}/references/_theme.md` via `read_vault_file(path='references/_theme.md')` —
    always read it first; the system prompt's Subject Theme section is only a fallback if the file is missing
  - Set the `← theme` vars in the copied CSS; base TOPIC_COLORS hues on the theme

STEP 3 — ASSEMBLE (no rewrite)
  - Copy assets/cheat-sheet.css into <style>, set the theme vars
  - Copy assets/cheat-sheet.js into <script> verbatim
  - Build the skeleton with the fixed element IDs (see templates/05-cheat-sheet.md)
  - Fill in CARDS (all kind:'formula') and TOPIC_COLORS
  - Every card: formula field with $$ delimiters AND unicode fallback AFTER them (see templates/05-cheat-sheet.md for the multi-CDN KaTeX + fallback rules)
  - The formula field reads `'$$…$$  <unicode version>'` — the unicode text sits OUTSIDE the delimiters so it survives the no-KaTeX fallback
  - #cardGrid must keep the engine's multi-column cascade layout (never a CSS grid; never fixed tall card heights)

STEP 4 — SELF-CHECK
  - Every formula passed dimensional analysis (units of RHS reduce to units of result)
  - At least one formula per topic verified with a numeric example (known textbook value)
  - Formulas match the wiki symbol-for-symbol — variables never renamed
  - Every card has all four parts: summary, formula, variables table with units, note with validity/trap
  - KaTeX delimiters present ($$…$$) with the unicode fallback text AFTER the delimiters

STEP 5 — SAVE & LOG
  - Call `write_study_object` with filename, tag="formula", and full HTML
  - Log to subjects/{subject}/wiki/log.md
```