#!/usr/bin/env python3
"""One-time migration: create .meta.json for all existing objects."""
import os
import json
import re
from datetime import datetime, timezone

VAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vaults")

OBJECT_TYPE_PREFIXES = {
    "mock-": "mock",
    "cheat-": "cheat",
    "mindmap-": "mindmap",
    "formula-": "formula",
    "flash-": "flash",
    "parcial-": "exam",
}
OBJECT_TYPE_KEYWORDS = {
    "examen": "mock",
    "practica": "mock",
    "summary": "cheat",
    "mapa": "mindmap",
    "concept": "cheat",
    "calculus": "formula",
    "flashcard": "flash",
    "card": "flash",
}

def infer_type(filename):
    for prefix, t in OBJECT_TYPE_PREFIXES.items():
        if filename.startswith(prefix):
            return t
    lower = filename.lower()
    for kw, t in OBJECT_TYPE_KEYWORDS.items():
        if kw in lower:
            return t
    return "note"

def migrate():
    obj_root = os.path.join(VAULT, "objects")
    if not os.path.isdir(obj_root):
        print("No objects directory")
        return
    count = 0
    for subject in os.listdir(obj_root):
        subj_dir = os.path.join(obj_root, subject)
        if not os.path.isdir(subj_dir):
            continue
        for fname in os.listdir(subj_dir):
            if fname.startswith(".") or not fname.endswith(".html"):
                continue
            if fname.endswith(".meta.json"):
                continue
            meta_path = os.path.join(subj_dir, f"{fname}.meta.json")
            if os.path.isfile(meta_path):
                continue
            tag = infer_type(fname)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"tag": tag, "created": datetime.now(timezone.utc).isoformat()}, f, indent=1)
            print(f"  + {subject}/{fname} -> tag: {tag}")
            count += 1
    print(f"\nDone. {count} objects migrated.")

if __name__ == "__main__":
    migrate()