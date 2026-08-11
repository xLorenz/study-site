# AGENTS.md

Single-file AI study companion: stdlib Python HTTP server + vanilla JS frontend. No framework, no build step, no tests, no linter, no CI. Verification is manual: `python server.py` (port 8081, from `config.yaml`/`.env`) then open http://localhost:8081 or hit `GET /api/health`.

## Dependencies (README is stale)

- Required: `pyyaml`, `openai` (used by `chat/llm.py` despite "zero dependencies" claim). No `requirements.txt`.
- `markitdown` must be a CLI on PATH — uploads convert via `subprocess` (`routes/_base.py:304`) and fail without it.
- Optional: `manim` + `ffmpeg` + a LaTeX distro for `write_study_video` (miKTeX pdflatex dir auto-prepended to PATH in `server.py`).

## Routing — the non-obvious part

`server.py` is a `BaseHTTPRequestHandler` with hardcoded string dispatch, and every handler method is monkey-patched onto the class by `register()` in `routes/__init__.py`. A new endpoint requires **two** edits: the dispatch branch in `server.py` (GET and/or POST) and the `register()` lambda in `routes/__init__.py`. After that, `setup_routes()` (called only under `__main__`) patches module-level `VAULT`/`STUDY_DIR`/etc. into every route module because they were imported with stale values — route modules must keep reading those config globals, never re-derive paths at call time.

Chat runs as a background thread task (`chat/state.py`) with a queue buffer; the frontend reconnects via SSE (`POST /api/chat-stream`) with 15s keepalive comments. Tests/experiments against chat should start a task with `chat-start` and drain `chat-stream`.

## Config & secrets

Load order: env vars → `config.yaml` → hardcoded defaults. `.env` is hand-parsed in `server.py` (no dotenv lib; lines are `KEY=VALUE`). LLM keys accept `NIM_API_KEY` / `OPENCODE_ZEN_API_KEY` env vars and also `nim_api_key` / `opencode_zen_api_key` in `config.yaml` (checked in `chat/llm.py:_resolve_api_key`). If you add a config key, respect this chain.

## LLM provīders

- Models live in `chat/types.py::AVAILABLE_MODELS` (Zen `deepseek-v4-flash-free` primary, NVIDIA NIM `z-ai/glm-5.2` fallback) plus `PROVIDER_FOR_MODEL` mapping them to `zen`/`nvidia`. Adding a model touches both.
- Every API call tries the requested model first, then falls back across all other models on **429/timeout only** (`stream_chat` and ingest `_run_tool_loop`). Chat: temperature 1, max_tokens 65536, reasoning content streamed for DeepSeek via `chat_template_kwargs`. Ingest: temperature 0.3, up to 300 tool rounds, logs to `.cache/ingest.log`.
- UI copy is mixed Spanish/English (e.g. the reasoning-only nudge "Continúa: …" in `chat/llm.py`); keep it that way, don't "clean up" the Spanish.

## Vault & naming conventions (enforced in code)

- User data lives in `vaults/` (gitignored). Subject = `vaults/subjects/<subject>/` with `raw/`, `wiki/`, `references/`, `.ingested.json` tracker; generated objects in `vaults/objects/<subject>/`.
- All tool filenames go through `_normalize_filename` (`chat/tools.py`): lowercase, hyphens only — so "concept" files MUST be `lowercase-hyphen.md` to round-trip with wikilinks.
- `write_wiki_page` overwrites except `wiki/log.md` which appends; colliding study objects get `-v2` suffixes; tags are max 7 lowercase letters stored in `<file>.html.meta.json` sidecars.
- Wiki pages need YAML frontmatter (`title, created, type, tags, source_url`) per ingest prompt; every `[[wikilink]]` should resolve to a real page.
- Icons unless needed otherwise: the README's `subject_themes.json` is gone — colors come from a curated palette in `routes/_base.py` (cycles after 10, random start offset per restart).

## Video rendering

`write_study_video` writes the script to `.cache/manim/`, runs `python -m manim render -ql <script> <scene>` (subprocess, 600s timeout), then base64-embeds the MP4 straight into the HTML object file. Render output goes to `.cache/manim/media/videos/<scene>/480p15/`. Quality knob: `MANIM_RENDER_QUALITY` in `chat/types.py` (`ql` default).

## Skills

`chat/skills/<name>/SKILL.md` — served to the model via the `read_skill` tool and over HTTP at `/skill/<name>`. `study-professor` (base persona) is always loaded; `study-object-templates` and `manim-video` are loaded on demand. If you add a skill, update the `read_skill` tool description's skill list too.