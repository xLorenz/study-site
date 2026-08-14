# Formula Deck Verification

A formula deck is a reference the student will trust under exam pressure — every formula must be correct, unambiguous, and consistent with the source material. This file is the verification methodology. Read it before writing any formula card.

## Before writing: gather

- Read the raw practice files AND the wiki: formulas often appear in the wiki with derivation context (units, when they apply) that the raw notes omit.
- Note for each formula: **the name as used in the material**, the exact symbols/variables as used in the material (do not rename variables — a student's notes use the same symbols), the units, and the validity conditions (e.g. "válida para campos uniformes", "para conductores rectos e infinitos").
- Collect only formulas the material actually uses. 15-30 depending on subject breadth. Don't import formulas from general knowledge that don't appear in the course — the deck must match the course.

## Every card must answer four questions

1. **What does it compute?** — the `.formula-desc`: one line in the material's own language ("campo eléctrico de un plano infinito cargado").
2. **The formula itself** — `.formula`, monospace, using the material's exact symbols. Use `<span class="f-sym">`/`f-op`/`f-num` or a `.code > pre` block; never render math as an image.
3. **What is every variable?** — `.formula-vars`: one row per symbol with name AND unit. A table with "x: posición" is not enough — "x: posición (m)". Units are where students get burned.
4. **When does it apply / what's the trap?** — `.formula-note`: validity conditions, units of the result, sign conventions, or the classic pitfall for that formula (e.g. Gauss: "elegir una superficie gaussiana apropiada; flujo nulo no implica campo nulo").

## Verification passes (do all three)

### Pass 1 — Dimensional analysis (units)
Every formula must be dimensionally consistent. Check that the RHS units reduce to the LHS units. For physics: force formulas end in N (kg·m/s²), energy in J, fields in V/m or T. If a formula fails dimensional analysis, it is wrong — fix it.

### Pass 2 — Numeric sanity check
Pick one card and verify its formula with a real numeric example:
- Derive a known result: for E = σ/(2ε₀), plug σ = 1 nC/m² → E ≈ 56.5 V/m. If the formula can't reproduce a known textbook value, re-check the constant (ε₀, μ₀, 1/4πε₀, 2 vs 4 in denominators are the classic failure points).
- Check a degenerate case: does the formula give the expected limit when a variable → 0 or → ∞? (e.g. campo de un alambre infinito → 0 cuando r → ∞ ✓; B en el centro de una espira con R → ∞ → 0 ✓).

### Pass 3 — Cross-check with the wiki
The formula in the card must match the wiki page for that concept, symbol for symbol. If the wiki writes q₁q₂/r² and the card writes q₁q₂/d², the card is wrong regardless of which is physically right — the deck must be consistent with the course material.

## Common failure patterns (check these specifically)

- **Missing 4πε₀ / μ₀ / 2π factors** — the most common silent error. Always pass 1 + 2.
- **Inverted ratios** — V = kQ/r vs V = kr/Q; verify with units.
- **Sign conventions** — work vs potential energy, attraction vs repulsion. State the sign convention in `.formula-note` when it matters.
- **Validity conditions omitted** — the formula is right but silently inapplicable to the student's problem (Gauss for symmetric distributions, energy for uniform fields). The `.formula-note` is where this lives.
- **Variables renamed or reordered** vs the course material.
- **Units mixed** — nC vs C, cm vs m. If the material works in nC, either convert to SI in the card or state the convention in the note.

## Self-check checklist (run before saving)

1. Every formula passed dimensional analysis (Pass 1).
2. At least one formula per topic group verified with a numeric example (Pass 2).
3. Formulas match the wiki symbol-for-symbol (Pass 3).
4. Every card has all four parts: desc, formula, vars table with units, note with validity/trap.
5. No formulas outside the course material.