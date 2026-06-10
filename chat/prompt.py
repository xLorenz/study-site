"""System prompt construction for the study chat system."""

import os


def read_skill_content(skill_name):
    """Read SKILL.md content (minus YAML frontmatter) from ~/.hermes/skills/study/{name}/
    or ~/.hermes/skills/creative/{name}/ if not found."""
    search_paths = [
        os.path.expanduser(f"~/.hermes/skills/study/{skill_name}"),
        os.path.expanduser(f"~/.hermes/skills/creative/{skill_name}"),
    ]
    skill_path = None
    for sp in search_paths:
        candidate = os.path.join(sp, "SKILL.md")
        if os.path.isfile(candidate):
            skill_path = candidate
            break
    if skill_path is None:
        return f"<!-- {skill_name} skill not found -->"
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Strip YAML frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()
    return content


def build_chat_system_prompt(subject):
    """Build the complete system prompt for a chat session."""
    sections = []

    # 0. Subject identity (explicit so the model knows what it's teaching)
    sections.append(f"You are a university professor currently teaching the subject **{subject}**.\nEvery answer you give must be grounded in this subject's materials.")

    # 1. Study professor persona
    professor = read_skill_content("study-professor")
    sections.append(professor)

    # 2. Study object templates
    templates = read_skill_content("study-object-templates")
    sections.append(templates)

    # 3. Manim video production reference (concise guide for script writing)
    manim_guide = """
## Manim Video Production — Quick Guide

Write animated math/concept videos using `write_study_video` tool.

### Script structure
```python
from manim import *

class MyVideoName(Scene):
    def construct(self):
        # Background: set with a hex string or leave default (#1C1C1C works fine)
        self.camera.background_color = "#1C1C1C"
        title = Text("Concept Name", font_size=48, color=BLUE, font="Menlo")
        self.play(Write(title), run_time=1.5)
        self.wait(0.5)
        # ... more animations ...
```

### Key rules
1. **Use `Scene`**, NOT `Slide` — this tool renders a single video, not slides
2. **Set `self.camera.background_color`** to your preferred dark color (hex string works fine now)
3. **Avoid run_time under 0.3** — too fast to see
4. **Use `font="Menlo"`** for monospace text
5. **Add `self.wait(0.5-1.0)`** after animations for breathing room
6. **Use `self.add_subcaption("text", duration=2)`** for accessibility
7. **FadeOut at scene end**: `self.play(FadeOut(Group(*self.mobjects)))`
8. **Colors**: use named constants — BLUE, GREEN, YELLOW, RED, PURPLE, ORANGE, WHITE, GREY
9. **Use `self.camera.frame.save_state()` / `self.play(Restore(self.camera.frame))`** for camera moves

### Common patterns
- `Write(text)` for text appearing
- `Create(shape)` for shapes drawing
- `Transform(mobj1, mobj2)` for morphing
- `FadeIn(mobj)` / `FadeOut(mobj)` for fade transitions
- `self.play(mobj.animate.shift(UP))` for movement
- `VGroup(text, arrow, formula)` to group elements
- `MathTex(r"\\\\frac{1}{2}")` for LaTeX (always use raw strings)
- `self.wait(N)` pauses N seconds
- `self.play(Create(Axes()), run_time=2)` then plot with `graph = axes.plot(...)`

### When to use
Call `write_study_video` for: math concept animations, algorithm walkthroughs, step-by-step derivations, visual tutorials, data visualizations, any concept where animation explains better than static text.
"""
    sections.append(manim_guide)

    # 4. Subject SCHEMA.md
    vault_dir = os.path.expanduser("~/study-vault")
    schema_path = os.path.join(vault_dir, "subjects", subject, "SCHEMA.md")
    if os.path.isfile(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_content = f.read()
        sections.append(f"## Subject Schema\n\n{schema_content}")
    else:
        sections.append("<!-- No SCHEMA.md found for this subject -->")

    # 5. Subject index.md (overview of raw materials and relationships)
    index_path = os.path.join(vault_dir, "subjects", subject, "index.md")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index_content = f.read()
        sections.append(f"## Subject Index\n\n{index_content}")
    else:
        sections.append("<!-- No index.md found for this subject -->")

    # 6. Behavioral instructions
    instructions = """## Behavioral Instructions

1. Use tools when possible:
 - `write_study_object` when asked to create practice objects (exams, cheat-sheets, mind maps, diagrams, etc.) or when visually explaining something
 - `write_study_video` when asked for animated explanations, math visualizations, algorithm walkthroughs, step-by-step concept animations, or visual tutorials — write a manim Slide script, render it, and save as self-contained HTML
 - `read_vault_file` when asked subject-related questions — read from wiki/ for specific concepts, read from raw/ for general questions
2. The study-professor skill, study-object-templates skill, manim-video skill, and SCHEMA.md are your pre-loaded context — take them into account for every message
3. Be concise, be professional, not friendly. Explain only what's necessary and what the user asks. Don't bloat your message with unnecessary words
4. **ALWAYS** use `write_study_video` OVER `write_study_object` when an animation or step-by-step visual walkthrough would explain the concept better than a static HTML page. The tool works — manim IS available, it renders server-side and produces a self-contained HTML file. Do NOT write JS/HTML animations yourself, do NOT say "manim is not available" — just call the tool.
5. Use [[wikilinks]] when referring to concepts available in the wiki to point the user to the wiki page"""
    sections.append(instructions)

    return "\n\n".join(sections)
