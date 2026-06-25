# Multi-Topic Exam: Exercise Selection Methodology

When the user requests a comprehensive multi-topic exam ("parcial que incluya los temas X, Y, Z"), the key challenge is selecting the right exercises so the exam is coherent, covers all topics, and doesn't exceed reasonable length.

## Approach used for Física II (9 exercises, 7 practice files)

### Step 1: Read ALL raw practice files
Do NOT rely on wiki summaries alone — read `subjects/{subject}/raw/practica-*.md` for the actual exercises with their full text. The wiki summaries often omit exercise specifics needed to judge difficulty.

### Step 2: Map topics to exercises
For each topic the user listed, scan the corresponding practice file and identify:
- **Hardest exercises** that combine multiple concepts (e.g. "cascarón esférico + Gauss + densidad de carga + conexión a tierra")
- **Most common exam problems** — problems that appear in multiple variants or are classic for that topic (e.g. "circuito de Kirchhoff de 3 mallas", "selector de velocidades + espectrómetro de masas")
- **Exercises with multiple sub-questions** (a, b, c, d, e) that build from simple to complex

### Step 3: Cluster by concept
Group closely related topics into single exercises:
- Gauss + conductores + densidad superficial → 1 exercise (cascarón esférico con carga puntual)
- Flujo eléctrico + Gauss + láminas paralelas + densidad σ → 1 exercise
- Potencial eléctrico + trabajo + energía de configuración → 1 exercise
- Kirchhoff + Ohm + potencia → 1 exercise
- Biot-Savart + Ampère + Lorentz → 1 exercise

### Step 4: Design sub-questions
Each exercise gets 4-5 sub-questions building in complexity:
- (a) basic calculation or qualitative justification
- (b) quantitative with same setup
- (c) more complex calculation requiring integration of concepts
- (d) "what if" variation (e.g. connect to ground, reverse charge sign)
- (e) extension to new situation

### Step 5: Write complete solutions
Each answer is pre-authored with:
- Step-by-step reasoning (not just the final number)
- `.result` blocks for final numeric/vector answers
- Verification checks where possible (e.g. "V₁+V₂ = V₁₂ ✓")

## Pitfalls
- **Don't pick too many exercises** — 8-10 is the sweet spot for a 3-hour exam covering 15+ topics
- **Don't skip requested topics** — even if a topic has fewer natural exercises, include at least one
- **Don't add topics not requested** — the user's list is the boundary
- **Don't copy exercises verbatim** — adapt them: change numbers, combine parts from different exercises, add new sub-questions that bridge concepts
- **Check your math** — physics numbers are easy to miscalculate; verify with alternative methods (energy conservation, Gauss law, Kirchhoff consistency)
