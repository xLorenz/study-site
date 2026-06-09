"""Tool definitions and execution for the study chat system."""

import json
import os
import re

from .types import VAULT_DIR


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

    objects_dir = os.path.join(VAULT_DIR, "subjects", subject, "objects")
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

    else:
        return {"error": f"Unknown tool: {tool_call_name}"}
