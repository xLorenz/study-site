"""Tool definitions and execution for the study chat system."""

import base64
import glob
import json
import os
import re
import subprocess
import sys
import textwrap

from .types import VAULT_DIR, MANIM_DIR, MANIM_RENDER_QUALITY


def get_tool_definitions():
    """Return OpenAI function-calling tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_vault_file",
                "description": "Read a file from the current subject's vault directory. "
                               "Use this when asked subject-related questions. "
                               "Read from wiki/ for specific concepts, read from raw/ for general questions.",
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
                            "description": "Desired filename (e.g. 'mock-exam-1', 'cheat-sheet-vectors'). Extension will be enforced to .html"
                        },
                        "html_content": {
                            "type": "string",
                            "description": "Full HTML content of the study object. Must include DOCTYPE, html, head, and body tags."
                        }
                    },
                    "required": ["filename", "html_content"]
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
                            "description": "Full Python manim script using Slide from manim_slides. "
                                           "Must import: from manim import *, from manim_slides import Slide. "
                                           "Each scene is a class extending Slide. Use self.pause() between slides. "
                                           "Use DEFAULT_BG_COLOR constant for background. "
                                           "NO self.camera.background_color assignment."
                        },
                        "scene_name": {
                            "type": "string",
                            "description": "The class name of the scene to render (must match a Slide subclass in the script)."
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
        # Try fuzzy resolution: basename search in wiki/, raw/, references/
        basename = os.path.basename(path)
        for search_dir in ["wiki", "raw", "references"]:
            search_path = os.path.join(subject_dir, search_dir)
            if not os.path.isdir(search_path):
                continue
            for root, dirs, fnames in os.walk(search_path):
                for f in fnames:
                    if f == basename or f == basename + ".md" or os.path.splitext(f)[0] == os.path.splitext(basename)[0]:
                        found_path = os.path.join(root, f)
                        if os.path.realpath(found_path).startswith(real_subject_dir + os.sep):
                            with open(found_path, "r", encoding="utf-8") as fh:
                                return {"content": fh.read(), "path": os.path.relpath(found_path, subject_dir)}
        return {"error": f"File not found: {path}"}

    with open(real_target, "r", encoding="utf-8") as f:
        content = f.read()

    rel_path = os.path.relpath(real_target, subject_dir)
    return {"content": content, "path": rel_path}


def write_study_object(subject, filename, html_content):
    """Write an HTML study object with versioned collision handling."""
    filename = _normalize_filename(filename)
    if not filename.endswith(".html"):
        filename += ".html"

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

    with open(real_target, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "path": os.path.relpath(real_target, VAULT_DIR),
        "filename": os.path.basename(real_target),
        "subject": subject
    }


def write_wiki_page(subject, filename, content):
    """Write a wiki markdown page with path traversal protection."""
    # Normalize: strip .md if present, normalize base, add .md back
    base = filename
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
        content = existing.rstrip() + "\\n" + content.lstrip()

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

    from datetime import datetime
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


def write_study_video(subject, filename, script, scene_name):
    """Render a manim script and save as a self-contained HTML with embedded video."""
    filename = _normalize_filename(filename)
    if not filename.endswith(".html"):
        filename += ".html"

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
    script_path = os.path.join(manim_dir, f"{scene_name}.py")
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
        quality_name = f"{MANIM_RENDER_QUALITY}p15"
        mp4_path = os.path.join(
            manim_dir, "media", "videos", scene_name, quality_name, f"{scene_name}.mp4"
        )
        if not os.path.isfile(mp4_path):
            # Try alternate quality name (without p15 suffix)
            mp4_path = os.path.join(
                manim_dir, "media", "videos", scene_name, MANIM_RENDER_QUALITY, f"{scene_name}.mp4"
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

    return {
        "path": os.path.relpath(real_target, VAULT_DIR),
        "filename": os.path.basename(real_target),
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
        if not filename or not html_content:
            return {"error": "Missing 'filename' or 'html_content' argument"}
        return write_study_object(subject, filename, html_content)

    elif tool_call_name == "write_study_video":
        filename = args.get("filename", "")
        script = args.get("script", "")
        scene_name = args.get("scene_name", "")
        if not filename or not script or not scene_name:
            return {"error": "Missing 'filename', 'script', or 'scene_name' argument"}
        return write_study_video(subject, filename, script, scene_name)

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

    else:
        return {"error": f"Unknown tool: {tool_call_name}"}
