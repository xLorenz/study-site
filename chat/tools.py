"""Tool definitions and execution for the study chat system."""

import base64
import glob
import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timezone

from .types import VAULT_DIR, MANIM_DIR, MANIM_RENDER_QUALITY, STUDY_DIR


def get_tool_definitions():
    """Return OpenAI function-calling tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_vault_file",
                "description": "Read a file from the current subject's vault directory. "
                               "Use this when asked subject-related questions. "
                               "Prefer wiki/ pages (including wiki/src-{name}.md source summaries), "
                               "only fall back to raw/ if the concept isn't covered in wiki/.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path within the subject's vault directory (e.g. 'wiki/concept-name.md', 'raw/source-file.md')"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_study_object",
                "description": "Create an HTML study object (exam, cheat-sheet, mind-map, flashcards, formula deck) "
                               "when asked to create practice materials or visually explain something.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Desired filename (e.g. 'exam-1', 'vectors-mindmap'). Extension will be enforced to .html"
                        },
                        "html_content": {
                            "type": "string",
                            "description": "Full HTML content of the study object. Must include DOCTYPE, html, head, and body tags."
                        },
                        "tag": {
                            "type": "string",
                            "description": "Optional free-form tag (max 7 lowercase letters only). Describe the object type/content: 'mock', 'mindmap', 'flash', 'cheat', 'exam', 'formula', 'solutions', etc. Used for UI badge with deterministic color."
                        }
                    },
                    "required": ["filename", "html_content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_study_object",
                "description": "Update an existing HTML study object's content and/or tag. "
                               "Use this to fix errors, improve content, or retag an existing object. "
                               "Overwrites the file in-place (no versioning).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Existing filename (e.g. 'exam-1.html'). Must match exactly."
                        },
                        "html_content": {
                            "type": "string",
                            "description": "Optional new HTML content to overwrite the file."
                        },
                        "tag": {
                            "type": "string",
                            "description": "Optional new tag (max 7 lowercase letters only). Overwrites the existing tag."
                        }
                    },
                    "required": ["filename"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_study_video",
                "description": "Create an animated manim video explaining a concept. "
                               "Use this when asked for animated explanations, math/algorithm visualizations, "
                               "step-by-step concept walkthroughs, or visual tutorials. "
                               "Produces a self-contained HTML file with embedded video.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Desired filename (e.g. 'sorting-algorithms', 'chain-rule'). Extension will be enforced to .html"
                        },
                        "script": {
                            "type": "string",
                            "description": "Full Python manim script. Load the `manim-video` skill via `read_skill` for complete guidelines (2D/3D, patterns, conventions). Minimal: `from manim import *`; class extending `Scene` or `ThreeDScene`; set `self.camera.background_color`."
                        },
                        "scene_name": {
                            "type": "string",
                            "description": "The class name of the scene to render (must match a Scene subclass in the script)."
                        },
                        "tag": {
                            "type": "string",
                            "description": "Optional free-form tag (max 7 lowercase letters only). Describe the video type: 'animation', 'video', 'viz', 'demo', etc. Used for UI badge with deterministic color."
                        }
                    },
                    "required": ["filename", "script", "scene_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_wiki_page",
                "description": "Write or update a wiki markdown page in the subject's wiki/ directory. "
                               "Use this to create source summaries, concept pages, or any wiki documentation. "
                               "The content must include YAML frontmatter (title, created, type, tags, source_url). "
                               "Use [[wikilinks]] to cross-reference other wiki pages. "
                               "Can also write to wiki/index.md and wiki/log.md for index/log updates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Filename for the wiki page (e.g. 'src-tp1-intro', 'cable-coaxial', 'index', 'log'). .md extension will be added if missing."
                        },
                        "content": {
                            "type": "string",
                            "description": "Full markdown content of the wiki page. Must include YAML frontmatter (title, created, type, tags, source_url) for new pages. May omit it for wiki/index.md and wiki/log.md updates."
                        }
                    },
                    "required": ["filename", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mark_file_ingested",
                "description": "Mark a raw file as having been fully processed (ingested). "
                               "Call this AFTER you have created all wiki pages derived from this raw file. "
                               "Updates the .ingested.json tracker so the file won't be processed again.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The raw filename (e.g. 'tp1-intro.md'). Must match exactly the filename in the raw/ directory."
                        }
                    },
                    "required": ["filename"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "highlight_node",
                "description": "Highlight one or more concept nodes in the knowledge graph. Use this when explaining concepts to visually guide the student.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nodes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Array of wikilink node names to highlight"
                        }
                    },
                    "required": ["nodes"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_skill",
                "description": "Read a skill definition from the chat/skills/ directory. "
                               "Use this to load creative/technical guidelines before generating content. "
                               "Available skills: manim-video, study-professor, study-object-templates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Skill directory name (e.g. 'manim-video', 'study-professor', 'study-object-templates')"
                        },
                        "path": {
                            "type": "string",
                            "description": "Optional sub-path within the skill directory (e.g. 'templates/01-mock-exam.md'). If omitted, reads SKILL.md."
                        }
                    },
                    "required": ["skill_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_design_notes",
                "description": "Write design notes, session plans, or object blueprints to the subject's references/ directory. "
                               "Use this for object design plans (before creating study objects), session notes, or any internal reference material. "
                               "The references/ folder is for internal design docs — not shown in the wiki index. "
                               "Creates folder on first write.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Desired filename (e.g. 'object-exam-1-design', 'session-notes'). .md extension added if missing."
                        },
                        "content": {
                            "type": "string",
                            "description": "Full markdown content (raw, no frontmatter required)."
                        }
                    },
                    "required": ["filename", "content"]
                }
            }
        }
    ]


def _normalize_filename(filename):
    """Normalize filename: lowercase, hyphens, strips non-alphanumeric chars."""
    name = filename.lower().strip()
    name = re.sub(r'[^a-z0-9\-]', '-', name)
    name = re.sub(r'-+', '-', name)
    name = name.strip('-')
    if not name:
        name = 'study-object'
    return name


def read_vault_file(subject, path):
    """Read a file from the subject's vault directory with path traversal protection."""
    subject_dir = os.path.join(VAULT_DIR, "subjects", subject)
    real_subject_dir = os.path.realpath(subject_dir)

    target = os.path.join(subject_dir, path)
    real_target = os.path.realpath(target)

    # Path traversal protection
    if not real_target.startswith(real_subject_dir + os.sep):
        return {"error": f"Path traversal detected: {path} is outside subject directory"}

    if not os.path.isfile(real_target):
        # Try fuzzy resolution: case-insensitive basename search in wiki/, raw/, references/
        basename_lower = os.path.basename(path).lower()
        base_no_ext = os.path.splitext(basename_lower)[0]
        for search_dir in ["wiki", "raw", "references"]:
            search_path = os.path.join(subject_dir, search_dir)
            if not os.path.isdir(search_path):
                continue
            for root, dirs, fnames in os.walk(search_path):
                for f in fnames:
                    fl = f.lower()
                    if fl == basename_lower or fl == basename_lower + ".md" or os.path.splitext(fl)[0] == base_no_ext:
                        found_path = os.path.join(root, f)
                        if os.path.realpath(found_path).startswith(real_subject_dir + os.sep):
                            with open(found_path, "r", encoding="utf-8") as fh:
                                return {"content": fh.read(), "path": os.path.relpath(found_path, subject_dir)}
        return {"error": f"File not found: {path}"}

    with open(real_target, "r", encoding="utf-8") as f:
        content = f.read()

    rel_path = os.path.relpath(real_target, subject_dir)
    return {"content": content, "path": rel_path}


def write_study_object(subject, filename, html_content, tag=None):
    """Write an HTML study object with versioned collision handling."""
    filename = _normalize_filename(filename)
    if not filename.endswith(".html"):
        filename += ".html"

    # Validate tag: max 7 lowercase letters only
    if tag:
        tag = tag.strip().lower()
        tag = re.sub(r'[^a-z]', '', tag)[:7]
        if not tag:
            tag = None

    objects_dir = os.path.join(VAULT_DIR, "objects", subject)
    os.makedirs(objects_dir, exist_ok=True)

    target_path = os.path.join(objects_dir, filename)

    # Verify path is within objects dir
    real_objects_dir = os.path.realpath(objects_dir)
    real_target = os.path.realpath(target_path)
    if not real_target.startswith(real_objects_dir + os.sep):
        return {"error": "Path traversal prevented"}

    # Versioned collision handling
    if os.path.exists(real_target):
        base, ext = os.path.splitext(filename)
        version = 2
        while os.path.exists(os.path.join(objects_dir, f"{base}-v{version}{ext}")):
            version += 1
        target_path = os.path.join(objects_dir, f"{base}-v{version}{ext}")
        real_target = os.path.realpath(target_path)

    # Basic HTML well-formedness check
    warnings = []
    content_lower = html_content.lower()
    if "<!doctype html" not in content_lower and "<html" not in content_lower:
        warnings.append("Missing DOCTYPE or <html> tag")
    if "</html>" not in content_lower:
        warnings.append("Missing closing </html> tag")

    with open(real_target, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Write metadata file with tag
    if tag:
        meta_path = os.path.join(objects_dir, f"{os.path.basename(real_target)}.meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"tag": tag, "created": datetime.now(timezone.utc).isoformat()}, f)

    result = {
        "path": os.path.relpath(real_target, VAULT_DIR),
        "filename": os.path.basename(real_target),
        "subject": subject,
        "tag": tag
    }
    if warnings:
        result["warnings"] = warnings
    return result


def update_study_object(subject, filename, html_content=None, tag=None):
    """Update an existing study object's content and/or tag in-place."""
    filename = _normalize_filename(filename)
    if not filename.endswith(".html"):
        filename += ".html"

    if tag:
        tag = tag.strip().lower()
        tag = re.sub(r'[^a-z]', '', tag)[:7]
        if not tag:
            tag = None

    objects_dir = os.path.join(VAULT_DIR, "objects", subject)
    target_path = os.path.join(objects_dir, filename)

    real_objects_dir = os.path.realpath(objects_dir)
    real_target = os.path.realpath(target_path)
    if not real_target.startswith(real_objects_dir + os.sep):
        return {"error": "Path traversal prevented"}

    if not os.path.isfile(real_target):
        return {"error": f"Object '{filename}' not found in subject '{subject}'"}

    if html_content is not None:
        with open(real_target, "w", encoding="utf-8") as f:
            f.write(html_content)

    if tag is not None:
        meta_path = os.path.join(objects_dir, f"{filename}.meta.json")
        existing = {}
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        meta = {"tag": tag, "created": existing.get("created", datetime.now(timezone.utc).isoformat())}
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)

    return {
        "path": os.path.relpath(real_target, VAULT_DIR),
        "filename": os.path.basename(real_target),
        "subject": subject,
        "tag": tag if tag is not None else None,
        "content_updated": html_content is not None,
        "tag_updated": tag is not None,
    }


def write_wiki_page(subject, filename, content):
    """Write a wiki markdown page with path traversal protection."""
    # Strip any directory prefix (e.g. "wiki/foo" → "foo") and normalize
    base = os.path.basename(filename)
    if base.endswith(".md"):
        base = base[:-3]
    base = _normalize_filename(base)
    filename = base + ".md"

    wiki_dir = os.path.join(VAULT_DIR, "subjects", subject, "wiki")
    os.makedirs(wiki_dir, exist_ok=True)

    target_path = os.path.join(wiki_dir, filename)
    real_wiki_dir = os.path.realpath(wiki_dir)
    real_target = os.path.realpath(target_path)

    # Path traversal protection
    if not real_target.startswith(real_wiki_dir + os.sep):
        return {"error": "Path traversal prevented"}

    # Preserve wiki/index.md and wiki/log.md — append for log, overwrite for index
    if filename == "log.md" and os.path.isfile(real_target):
        with open(real_target, "r", encoding="utf-8") as f:
            existing = f.read()
        content = existing.rstrip() + "\n" + content.lstrip()

    with open(real_target, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "path": os.path.relpath(real_target, VAULT_DIR),
        "filename": filename,
        "subject": subject,
        "size_bytes": os.path.getsize(real_target),
    }


def mark_file_ingested(subject, filename):
    """Mark a raw file as ingested in .ingested.json."""
    filename = os.path.basename(filename)  # strip any directory prefix
    if not filename.endswith(".md"):
        filename += ".md"
    raw_dir = os.path.join(VAULT_DIR, "subjects", subject, "raw")
    raw_path = os.path.join(raw_dir, filename)

    # Verify the file exists
    if not os.path.isfile(raw_path):
        return {"error": f"Raw file not found: raw/{filename}"}

    # Read current ingested set
    ingested_path = os.path.join(raw_dir, ".ingested.json")
    ingested = set()
    if os.path.isfile(ingested_path):
        try:
            with open(ingested_path, encoding="utf-8") as f:
                data = json.load(f)
            ingested = set(data.get("ingested", []))
        except (json.JSONDecodeError, OSError):
            pass

    ingested.add(filename)

    with open(ingested_path, "w", encoding="utf-8") as f:
        json.dump({
            "ingested": sorted(ingested),
            "last_ingested": datetime.now().isoformat()
        }, f, indent=1)

    return {
        "marked": filename,
        "subject": subject,
        "total_ingested": len(ingested),
    }


def write_study_video(subject, filename, script, scene_name, tag=None):
    """Render a manim script and save as a self-contained HTML with embedded video."""
    filename = _normalize_filename(filename)
    if not filename.endswith(".html"):
        filename += ".html"

    # Validate tag: max 7 lowercase letters only
    if tag:
        tag = tag.strip().lower()
        tag = re.sub(r'[^a-z]', '', tag)[:7]
        if not tag:
            tag = None

    objects_dir = os.path.join(VAULT_DIR, "objects", subject)
    os.makedirs(objects_dir, exist_ok=True)

    real_objects_dir = os.path.realpath(objects_dir)
    target_path = os.path.join(objects_dir, filename)
    real_target = os.path.realpath(target_path)
    if not real_target.startswith(real_objects_dir + os.sep):
        return {"error": "Path traversal prevented"}

    # Versioned collision handling
    if os.path.exists(real_target):
        base, ext = os.path.splitext(filename)
        version = 2
        while os.path.exists(os.path.join(objects_dir, f"{base}-v{version}{ext}")):
            version += 1
        target_path = os.path.join(objects_dir, f"{base}-v{version}{ext}")
        real_target = os.path.realpath(target_path)

    # Prepare manim directory
    manim_dir = os.path.realpath(MANIM_DIR)
    os.makedirs(manim_dir, exist_ok=True)

    # Write script to file
    scene_name_clean = scene_name.replace("/", "_").replace("\\", "_")
    script_path = os.path.join(manim_dir, f"{scene_name_clean}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(script))

    quality_flag = f"-{MANIM_RENDER_QUALITY}"

    try:
        # Step 1: Render with manim
        render_result = subprocess.run(
            [sys.executable, "-m", "manim", "render", quality_flag, script_path, scene_name],
            capture_output=True, text=True, timeout=600, cwd=manim_dir
        )
        if render_result.returncode != 0:
            error_msg = render_result.stderr[-1500:] if render_result.stderr else render_result.stdout[-1500:]
            return {"error": f"Manim render failed: {error_msg}"}

        # Step 2: Find the rendered MP4
        QUALITY_DIR_MAP = {"l": "480p15", "m": "720p30", "h": "1080p60"}
        qkey = MANIM_RENDER_QUALITY.replace("q", "")  # "ql" → "l"
        quality_dir = QUALITY_DIR_MAP.get(qkey, "480p15")
        mp4_path = os.path.join(
            manim_dir, "media", "videos", scene_name, quality_dir, f"{scene_name}.mp4"
        )
        if not os.path.isfile(mp4_path):
            # Fallback: search for any mp4
            found = sorted(glob.glob(os.path.join(manim_dir, "media", "videos", scene_name, "**", f"{scene_name}.mp4"), recursive=True), key=os.path.getmtime, reverse=True)
            if found:
                mp4_path = found[0]
            else:
                return {"error": "Render completed but output MP4 not found"}

        # Step 3: Read MP4 and encode as base64
        with open(mp4_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode("ascii")

        subject_title = subject.replace("-", " ").title()
        scene_title = scene_name.replace("_", " ").replace("-", " ").title()

        # Step 4: Generate a simple, self-contained HTML with embedded video
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{scene_title} — {subject_title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0f0f14; display: flex; align-items: center; justify-content: center;
    min-height: 100vh; font-family: system-ui, -apple-system, sans-serif;
  }}
  .container {{ max-width: 100%; padding: 8px; }}
  video {{
    display: block; max-width: 100%; max-height: 90vh; width: 100%;
    border-radius: 12px; box-shadow: 0 4px 32px rgba(0,0,0,0.5);
    background: #000;
  }}
  .label {{
    text-align: center; padding: 12px 0 4px;
    color: #888; font-size: 13px; letter-spacing: 0.3px;
  }}
</style>
</head>
<body>
<div class="container">
  <video muted loop controls playsinline src="data:video/mp4;base64,{video_b64}"></video>
  <div class="label">{scene_title}</div>
</div>
</body>
</html>"""

        with open(real_target, "w", encoding="utf-8") as f:
            f.write(html)

        if not os.path.isfile(real_target):
            return {"error": "Failed to write output HTML"}

    except subprocess.TimeoutExpired:
        return {"error": "Manim render timed out (600s)"}
    except Exception as e:
        return {"error": f"Manim pipeline error: {e}"}

    # Write metadata file with tag
    if tag:
        meta_path = os.path.join(objects_dir, f"{os.path.basename(real_target)}.meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"tag": tag, "created": datetime.now(timezone.utc).isoformat()}, f)

    return {
        "path": os.path.relpath(real_target, VAULT_DIR),
        "filename": os.path.basename(real_target),
        "subject": subject,
        "size_bytes": os.path.getsize(real_target),
        "tag": tag
    }


def read_skill(skill_name, path=None):
    """Read a skill from chat/skills/ directory. Optional sub-path for reading template files."""
    skills_dir = os.path.join(STUDY_DIR, "chat", "skills")
    if path:
        skill_path = os.path.join(skills_dir, skill_name, path)
    else:
        skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")
    if os.path.isfile(skill_path):
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()
        return content
    if path:
        return f"<!-- Skill '{skill_name}/{path}' not found in chat/skills/ -->"
    return f"<!-- Skill '{skill_name}' not found in chat/skills/ -->"


def write_design_notes(subject, filename, content):
    """Write a design note to the subject's references/ directory."""
    base = os.path.basename(filename)
    if base.endswith(".md"):
        base = base[:-3]
    base = _normalize_filename(base)
    filename = base + ".md"

    refs_dir = os.path.join(VAULT_DIR, "subjects", subject, "references")
    os.makedirs(refs_dir, exist_ok=True)

    target_path = os.path.join(refs_dir, filename)
    real_refs_dir = os.path.realpath(refs_dir)
    real_target = os.path.realpath(target_path)
    if not real_target.startswith(real_refs_dir + os.sep):
        return {"error": "Path traversal prevented"}

    with open(real_target, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "path": os.path.relpath(real_target, VAULT_DIR),
        "filename": filename,
        "subject": subject,
        "size_bytes": os.path.getsize(real_target),
    }


def execute_tool(subject, tool_call_name, args_json_str):
    """Execute a tool by name with parsed JSON arguments."""
    try:
        args = json.loads(args_json_str)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON arguments: {e}"}

    if tool_call_name == "read_vault_file":
        path = args.get("path", "")
        if not path:
            return {"error": "Missing 'path' argument"}
        return read_vault_file(subject, path)

    elif tool_call_name == "write_study_object":
        filename = args.get("filename", "")
        html_content = args.get("html_content", "")
        tag = args.get("tag")
        if not filename or not html_content:
            return {"error": "Missing 'filename' or 'html_content' argument"}
        return write_study_object(subject, filename, html_content, tag)

    elif tool_call_name == "update_study_object":
        filename = args.get("filename", "")
        html_content = args.get("html_content", None)
        tag = args.get("tag", None)
        if not filename:
            return {"error": "Missing 'filename' argument"}
        if html_content is None and tag is None:
            return {"error": "Provide 'html_content' and/or 'tag' to update"}
        return update_study_object(subject, filename, html_content, tag)

    elif tool_call_name == "write_study_video":
        filename = args.get("filename", "")
        script = args.get("script", "")
        scene_name = args.get("scene_name", "")
        tag = args.get("tag")
        if not filename or not script or not scene_name:
            return {"error": "Missing 'filename', 'script', or 'scene_name' argument"}
        return write_study_video(subject, filename, script, scene_name, tag)

    elif tool_call_name == "write_wiki_page":
        filename = args.get("filename", "")
        content = args.get("content", "")
        if not filename or not content:
            return {"error": "Missing 'filename' or 'content' argument"}
        return write_wiki_page(subject, filename, content)

    elif tool_call_name == "mark_file_ingested":
        filename = args.get("filename", "")
        if not filename:
            return {"error": "Missing 'filename' argument"}
        return mark_file_ingested(subject, filename)

    elif tool_call_name == "highlight_node":
        nodes = args.get("nodes", [])
        if not isinstance(nodes, list) or len(nodes) == 0:
            return {"error": "Missing or empty 'nodes' array"}
        return {"highlight_nodes": nodes}

    elif tool_call_name == "read_skill":
        skill_name = args.get("skill_name", "")
        path = args.get("path", None)
        if not skill_name:
            return {"error": "Missing 'skill_name' argument"}
        return read_skill(skill_name, path)

    elif tool_call_name == "write_design_notes":
        filename = args.get("filename", "")
        content = args.get("content", "")
        if not filename or not content:
            return {"error": "Missing 'filename' or 'content' argument"}
        return write_design_notes(subject, filename, content)

    else:
        return {"error": f"Unknown tool: {tool_call_name}"}
