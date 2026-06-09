"""System prompt construction for the study chat system."""

import os


def read_skill_content(skill_name):
    """Read SKILL.md content (minus YAML frontmatter) from ~/.hermes/skills/study/{name}/"""
    skill_dir = os.path.expanduser(f"~/.hermes/skills/study/{skill_name}")
    skill_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_path):
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

    # 1. Study professor persona
    professor = read_skill_content("study-professor")
    sections.append(professor)

    # 2. Study object templates
    templates = read_skill_content("study-object-templates")
    sections.append(templates)

    # 3. Subject SCHEMA.md
    vault_dir = os.path.expanduser("~/study-vault")
    schema_path = os.path.join(vault_dir, "subjects", subject, "SCHEMA.md")
    if os.path.isfile(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_content = f.read()
        sections.append(f"## Subject Schema\n\n{schema_content}")
    else:
        sections.append("<!-- No SCHEMA.md found for this subject -->")

    # 4. Behavioral instructions
    instructions = """## Behavioral Instructions

1. Use tools when possible:
   - `write_study_object` when asked to create practice objects (exams, cheat-sheets, mind maps, diagrams, etc.) or when visually explaining something
   - `read_vault_file` when asked subject-related questions — read from wiki/ for specific concepts, read from raw/ for general questions
2. The study-professor skill, study-object-templates skill, and SCHEMA.md are your pre-loaded context — take them into account for every message
3. Be concise, be professional, not friendly. Explain only what's necessary and what the user asks. Don't bloat your message with unnecessary words
4. Use [[wikilinks]] when referring to concepts available in the wiki to point the user to the wiki page"""
    sections.append(instructions)

    return "\n\n".join(sections)
