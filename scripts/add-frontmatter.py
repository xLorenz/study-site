#!/usr/bin/env python3
"""Batch-add YAML frontmatter to all wiki files in a subject vault."""
import os, re, sys
from datetime import date

VAULT = os.path.expanduser("~/study-vault")
TYPE_MAP = {
    "concepts": "concept",
    "definitions": "definition",
    "formulas": "formula",
    "exercises": "exercise",
}

def to_title(name):
    """Convert kebab-case-filename to Title Case."""
    return name.replace("-", " ").title()

def has_frontmatter(text):
    return text.startswith("---\n")

def add_frontmatter(filepath, fname, dir_type):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    
    if has_frontmatter(content):
        return False  # already has frontmatter
    
    node_id = fname[:-3]  # strip .md
    fm = (
        "---\n"
        f"title: {to_title(node_id)}\n"
        f"type: {TYPE_MAP.get(dir_type, 'note')}\n"
        f"tags: []\n"
        f"created: {date.today()}\n"
        "---\n\n"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(fm + content)
    return True

subject = sys.argv[1] if len(sys.argv) > 1 else "poo"
subj_dir = os.path.join(VAULT, "subjects", subject)
count = 0

for dir_type in TYPE_MAP:
    dpath = os.path.join(subj_dir, dir_type)
    if not os.path.isdir(dpath):
        continue
    for fname in sorted(os.listdir(dpath)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(dpath, fname)
        if add_frontmatter(fpath, fname, dir_type):
            count += 1
            print(f"  + {dir_type}/{fname}")

print(f"\nDone. {count} files updated with frontmatter.")
