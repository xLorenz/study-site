"""System prompt construction for the study chat system."""

import os
from .types import VAULT_DIR, STUDY_DIR


def read_skill_content(skill_name):
    """Read SKILL.md content (minus YAML frontmatter) from chat/skills/{name}/"""
    skill_path = os.path.join(STUDY_DIR, "chat", "skills", skill_name, "SKILL.md")
    if not os.path.isfile(skill_path):
        return f"<!-- {skill_name} skill not found -->"
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()
    return content


def get_available_skills():
    """List all skills in chat/skills/ directory."""
    skills_dir = os.path.join(STUDY_DIR, "chat", "skills")
    if not os.path.isdir(skills_dir):
        return []
    skills = []
    for entry in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, entry, "SKILL.md")
        if os.path.isfile(skill_path):
            skills.append(entry)
    return skills


def build_chat_system_prompt(subject):
    """Build the complete system prompt for a chat session."""
    sections = []

    # 0. Subject identity
    sections.append(f"You are a university professor currently teaching the subject **{subject}**.\nEvery answer you give must be grounded in this subject's materials.")

    # Subject theme from vault (model-readable via read_vault_file(path='references/_theme.md'))
    theme_path = os.path.join(VAULT_DIR, "subjects", subject, "references", "_theme.md")
    if os.path.isfile(theme_path):
        with open(theme_path, encoding="utf-8") as f:
            theme_content = f.read()
    else:
        theme_content = f"# {subject} — Theme\n\nprimary: #6b7db3\nsecondary: #8fa4cc\naccent: #aec0de\nicon: 📚\n"
    sections.append(f"## Subject Theme\n\n{theme_content.strip()}\n\n"
                    "Use these colors when creating HTML study objects. "
                    "Title gradient = linear-gradient(135deg, primary, secondary). "
                    "Section headings = secondary (or accent). "
                    "Alert borders = accent with transparency."
                    )

    # 1. Study professor persona (always loaded)
    professor = read_skill_content("study-professor")
    sections.append(professor)

    # 2. Subject SCHEMA.md
    schema_path = os.path.join(VAULT_DIR, "subjects", subject, "SCHEMA.md")
    if os.path.isfile(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_content = f.read()
        sections.append(f"## Subject Schema\n\n{schema_content}")
    else:
        sections.append("<!-- No SCHEMA.md found for this subject -->")

    # 3. Subject index.md
    index_path = os.path.join(VAULT_DIR, "subjects", subject, "index.md")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index_content = f.read()
        sections.append(f"## Subject Index\n\n{index_content}")
    else:
        sections.append("<!-- No index.md found for this subject -->")

    # 4. Available Tools & Skills (scalable registry)
    skills = get_available_skills()
    tools = [
        "read_vault_file",
        "write_study_object",
        "write_study_video",
        "write_wiki_page",
        "mark_file_ingested",
        "highlight_node",
        "read_skill",
    ]
    tool_lines = "\n".join(f"  - `{t}`" for t in tools)
    skill_lines = "\n".join(f"  - `{s}` (via `read_skill`)"
                            for s in skills)
    sections.append(
        f"## Available Tools\n{tool_lines}\n\n## Available Skills (load via `read_skill`)\n{skill_lines}"
    )

    # 5. Behavioral instructions
    instructions = """## Behavioral Instructions

1. **Choose the right tool for the user's request:**
   - `read_vault_file` — subject questions; prefer `wiki/` pages (including `wiki/src-{name}.md` source summaries), fall back to `raw/` only if concept not covered in wiki
   - `write_study_object` — static study aids: exams, cheat-sheets, mind maps, flashcards, formula decks, interactive exams
   - `write_study_video` — animated explanations, math/algorithm visualizations, step-by-step walkthroughs where motion adds clarity
   - `write_wiki_page` — create/update curated wiki documentation
   - `write_design_notes` — internal design docs, object blueprints, session notes (writes to references/)
   - `mark_file_ingested` — after fully processing a raw file
   - `highlight_node` — visually guide the student in the knowledge graph
   - `read_skill` — load additional skill guidelines (e.g. `manim-video`, `study-object-templates`) when the task warrants it

2. **Study-professor skill and SCHEMA.md are your always-loaded context.** Additional skills are available via `read_skill` — load them when the task requires their specific guidance.

3. Be concise, professional, direct. Answer exactly what was asked. No fluff, no meta-commentary.

4. Use [[wikilinks]] when referring to concepts available in the wiki.

5. Use `highlight_node` when explaining concepts to visually guide the student in the graph.

6. Use `write_design_notes` for object design plans (before `write_study_object`), session notes, or internal reference docs. These go to `references/` and are not in the wiki index.

7. **Use multiple tool calls when needed.** If a question requires reading multiple files, call `read_vault_file` multiple times. If creating an object requires reading context first, chain the calls: read → design → create. Do not stop after one tool call if more information or actions are needed.

8. **Tags for study objects.** When calling `write_study_object` or `write_study_video`, you may pass an optional `tag` parameter (max 7 lowercase letters only, e.g. `mock`, `mindmap`, `flash`, `cheat`, `exam`, `formula`, `video`, `solutions`). These are **free-form** — pick whatever tag best describes the object's type or content. The UI assigns a deterministic color from the tag string."""
    sections.append(instructions)

    return "\n\n".join(sections)

