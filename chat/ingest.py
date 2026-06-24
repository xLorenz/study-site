"""Wiki ingest system — non-interactive LLM-powered wiki page generation.

Uses the same NVIDIA NIM client as the chat system, but runs as a
background task with no streaming and no frontend interaction.
The LLM has read_vault_file, write_wiki_page, and mark_file_ingested tools
to process raw files and create wiki pages following SCHEMA.md conventions.
"""

import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone

from .llm import get_llm_client, get_extra_body
from .tools import get_tool_definitions, execute_tool
from .types import VAULT_DIR, AVAILABLE_MODELS, PROVIDER_FOR_MODEL

# Override: ingests can be very long (NVIDIA API is slow, many files to process)
MAX_TOOL_ROUNDS = 300
LLM_MAX_TOKENS = 65536  # max output tokens per LLM response

from .types import CACHE_DIR
LOG_PATH = os.path.join(CACHE_DIR, "ingest.log")

# ---------------------------------------------------------------------------
# Logging setup — writes to both file and stderr
# ---------------------------------------------------------------------------
_logger = logging.getLogger("study.ingest")
_logger.setLevel(logging.DEBUG)

_file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8", mode="a")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
_logger.addHandler(_file_handler)

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setFormatter(logging.Formatter(
    "%(asctime)s | INGEST | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
_logger.addHandler(_stderr_handler)


def _now_iso() -> str:
    """ISO 8601 timestamp for logging."""
    return datetime.now(timezone.utc).isoformat()


def _get_uningested_files(subject: str) -> list[str]:
    """Return sorted list of .md files in raw/ not yet ingested."""
    raw_dir = os.path.join(VAULT_DIR, "subjects", subject, "raw")
    if not os.path.isdir(raw_dir):
        return []
    ingested_path = os.path.join(raw_dir, ".ingested.json")
    ingested = set()
    if os.path.isfile(ingested_path):
        try:
            with open(ingested_path, encoding="utf-8") as f:
                data = json.load(f)
            ingested = set(data.get("ingested", []))
        except (json.JSONDecodeError, OSError):
            pass
    return sorted(
        f for f in os.listdir(raw_dir)
        if f.endswith(".md") and f != ".ingested.json" and f not in ingested
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_ingest_prompt(subject: str, uningested_files: list[str]) -> str:
    """Build the system prompt for the ingest LLM.

    Instructs the LLM to read SCHEMA.md, process each raw file, create wiki
    pages using write_wiki_page, and track progress with mark_file_ingested.
    """
    file_list = "\n".join(f"- {f}" for f in uningested_files)

    prompt = f"""You are a NON-INTERACTIVE automated wiki ingest assistant for subject '{subject}'. Do NOT ask questions or wait for discussion — just DO the work.

Un-ingested raw files in vaults/subjects/{subject}/raw/:
{file_list}

You have THREE tools available:
1. read_vault_file(path) — Read any file from the subject's vault directory. Use this to read SCHEMA.md, raw files, and existing wiki pages.
2. write_wiki_page(filename, content) — Write a wiki markdown page to the subject's wiki/ directory. Content must include YAML frontmatter (title, created, type, tags, source_url) for new pages. Use [[wikilinks]] to cross-reference.
3. mark_file_ingested(filename) — Call this AFTER you have created ALL wiki pages derived from the raw file. Marks it in .ingested.json so it won't be processed again.

WORKFLOW — Follow this order for each un-ingested file:

STEP 1 — Read SCHEMA.md
Use read_vault_file(path='SCHEMA.md') to get the subject's page format, frontmatter, and interlinking rules.

If SCHEMA.md does NOT exist, use these defaults:
- Page format: markdown with YAML frontmatter
- Frontmatter fields: title, created, type, tags, source_url
- type: one of source_summary, concept, formula, definition, exercise
- tags: exactly ONE topic tag per page (e.g., tags: [arrays]). Pick the single most specific topic.
- source_url: path to the raw file this page derives from (exactly one source — do NOT list multiple files). E.g., source_url: raw/2026-cd-tp6.md
- Source summaries: name them src-{{base-name}} (e.g., src-2026-cd-tp6) — never reuse raw/ filenames
- Create BOTH a source summary page per raw file AND concept pages for each distinct concept
- Use [[wikilinks]] with exact lowercase-hyphen filenames (e.g., [[cable-coaxial]], not [[Cable Coaxial]])
- Every concept wikilinked MUST have its own page — no orphan wikilinks
- End each concept page with a "## Related concepts" section
- Page names: lowercase-with-hyphens.md (no spaces, no special chars)

STEP 2 — Process each raw file
For each un-ingested raw .md file:
1. Read it with read_vault_file(path='raw/<filename>')
2. Follow SCHEMA.md conventions for page format
3. Create source summary page(s) with write_wiki_page
4. Create concept page(s) for distinct concepts with write_wiki_page
5. After ALL pages for this file are created, call mark_file_ingested(filename='<filename>')

STEP 3 — Final steps
After ALL files are processed:
1. Update wiki/index.md with new pages and one-line descriptions (read existing index.md first, then write updated version)
2. Append an entry to wiki/log.md with the date, source name, and what changed

RULES:
- Preserve existing wiki pages — never overwrite files you did not create unless updating index.md or log.md
- Never modify anything in raw/ (only mark_file_ingested touches .ingested.json)
- Be thorough — create high-quality wiki pages with proper structure, examples, and [[wikilinks]]
- This is NON-INTERACTIVE — never ask questions or wait for input

WHEN COMPLETELY DONE, write a brief summary of what you created."""
    return prompt


# ---------------------------------------------------------------------------
# Non-streaming multi-round tool loop
# ---------------------------------------------------------------------------

def _run_tool_loop(
    messages: list[dict],
    subject: str,
    model: str,
    on_progress: callable = None,
) -> dict:
    """Run a non-streaming multi-round tool-calling loop.

    Tries primary provider first (determined by PROVIDER_FOR_MODEL).
    On 429/timeout, falls back to the next provider in the list.

    Args:
        messages: List of message dicts starting with system prompt + user message.
        subject: Subject name (for tool execution).
        model: Model name to use.
        on_progress: Optional callback(event_dict) called after each tool execution.

    Returns:
        dict with keys: content, model, pages_created, tokens_used, status
    """
    # Build ordered list of (provider, model) pairs to try
    from .llm import get_llm_client, get_extra_body, _is_429_error
    primary_provider = PROVIDER_FOR_MODEL.get(model, "nvidia")
    if primary_provider == "zen":
        # Full fallback chain: Zen → NVIDIA v4-pro → v4-flash → glm-5.1
        provider_chain = [
            ("zen", model),
            ("nvidia", "deepseek-ai/deepseek-v4-pro"),
            ("nvidia", "deepseek-ai/deepseek-v4-flash"),
            ("nvidia", "z-ai/glm-5.1"),
        ]
    else:
        provider_chain = [("nvidia", model)]

    tools = get_tool_definitions()
    # Ingest only needs read_vault_file, write_wiki_page, mark_file_ingested
    ingest_tool_names = {"read_vault_file", "write_wiki_page", "mark_file_ingested"}
    tools = [t for t in tools if t["function"]["name"] in ingest_tool_names]

    # Active provider (set after first successful call, persists across rounds)
    active_provider = None
    active_model = None
    active_client = None

    def _try_chain(messages, tools, chain_idx_start=0):
        """Try API call across the provider chain. Returns (response, chain_index) on success."""
        for idx in range(chain_idx_start, len(provider_chain)):
            prov, mdl = provider_chain[idx]
            try:
                client = get_llm_client(prov)
                extra_body = get_extra_body(mdl, prov)
                resp = client.chat.completions.create(
                    model=mdl,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    stream=False,
                    extra_body=extra_body,
                    temperature=0.3,
                    max_tokens=LLM_MAX_TOKENS,
                )
                return resp, idx
            except Exception as e:
                _logger.warning(f"Provider '{prov}'/'{mdl}' failed: {e}")
                if not _is_429_error(e):
                    # Non-rate-limit error on first attempt — still fall through to retry
                    if idx == 0 and len(provider_chain) > 1:
                        _logger.info(f"  Falling back to next provider...")
                        continue
                    raise  # propagate to outer retry logic
                # 429 — try next provider
                continue
        return None, -1  # all providers failed

    round_num = 0
    pages_created = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    final_content = ""
    final_model = model
    status = "complete"

    while round_num < MAX_TOOL_ROUNDS:
        _logger.info(f"LLM round {round_num + 1} starting ({len(messages)} messages in context)")

        try:
            # Try active provider first (if known), otherwise start the chain
            if active_provider is not None:
                # Use existing active provider
                extra_body = get_extra_body(active_model, active_provider)
                response = active_client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    stream=False,
                    extra_body=extra_body,
                    temperature=0.3,
                    max_tokens=LLM_MAX_TOKENS,
                )
            else:
                # First call — try provider chain
                response, chain_idx = _try_chain(messages, tools)
                if response is None:
                    raise Exception(f"All providers failed for round {round_num + 1}")
                prov, mdl = provider_chain[chain_idx]
                active_provider = prov
                active_model = mdl
                active_client = get_llm_client(prov)
        except Exception as e:
            _logger.error(f"LLM API call failed on round {round_num + 1}: {e}")
            _logger.debug(traceback.format_exc())
            # Retry on transient errors (5xx, timeouts, network blips) — up to 3 attempts
            status = getattr(e, 'status_code', 0) or getattr(e, 'code', 0)
            is_transient = status == 0 or status >= 500 or 'timeout' in str(e).lower() or '504' in str(e)
            if is_transient:
                recovered = False
                for retry in range(3):
                    wait = 5 * (2 ** retry)
                    _logger.info(f"  Retry {retry + 1}/3 in {wait}s...")
                    time.sleep(wait)
                    try:
                        if active_provider is not None:
                            # Use active provider for retry
                            retry_extra = get_extra_body(active_model, active_provider)
                            response = active_client.chat.completions.create(
                                model=active_model,
                                messages=messages,
                                tools=tools,
                                tool_choice="auto",
                                stream=False,
                                extra_body=retry_extra,
                                temperature=0.3,
                                max_tokens=LLM_MAX_TOKENS,
                            )
                        else:
                            # No active provider yet — try chain from start
                            response, chain_idx = _try_chain(messages, tools)
                            if response is None:
                                raise Exception("All providers failed on retry")
                            prov, mdl = provider_chain[chain_idx]
                            active_provider = prov
                            active_model = mdl
                            active_client = get_llm_client(prov)
                        recovered = True
                        break
                    except Exception as e2:
                        _logger.error(f"  Retry {retry + 1}/3 failed: {e2}")
                        last_exception = e2
                if not recovered:
                    return {
                        "content": final_content,
                        "model": final_model,
                        "pages_created": pages_created,
                        "tokens_used": total_prompt_tokens + total_completion_tokens,
                        "status": f"api_error (all retries failed): {last_exception}",
                    }
            else:
                # Non-transient error — return immediately
                return {
                    "content": final_content,
                    "model": final_model,
                    "pages_created": pages_created,
                    "tokens_used": total_prompt_tokens + total_completion_tokens,
                    "status": f"api_error: {e}",
                }

        choice = response.choices[0]
        msg = choice.message
        final_model = response.model

        # Track token usage
        if hasattr(response, "usage") and response.usage:
            total_prompt_tokens += response.usage.prompt_tokens or 0
            total_completion_tokens += response.usage.completion_tokens or 0
            _logger.debug(
                f"Round {round_num + 1}: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}"
            )

        # Handle tool calls
        if msg.tool_calls and len(msg.tool_calls) > 0:
            _logger.info(f"Round {round_num + 1}: {len(msg.tool_calls)} tool call(s)")

            # Collect the assistant message with tool calls
            assistant_msg = {
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [],
            }
            tool_result_messages = []

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = tc.function.arguments
                tc_id = tc.id or f"tc_{os.urandom(4).hex()}"

                # Log the call
                args_preview = fn_args[:300] + "..." if len(fn_args) > 300 else fn_args
                _logger.info(f"  Tool: {fn_name}({args_preview})")

                # Add to assistant message
                assistant_msg["tool_calls"].append({
                    "id": tc_id,
                    "type": "function",
                    "function": {"name": fn_name, "arguments": fn_args},
                })

                # Execute
                try:
                    result = execute_tool(subject, fn_name, fn_args)
                except Exception as e:
                    _logger.error(f"  Tool execution failed: {e}")
                    result = {"error": f"Tool execution error: {e}"}

                result_str = json.dumps(result, ensure_ascii=False)
                # Truncate very long results for logging
                log_result = result_str[:500] + "..." if len(result_str) > 500 else result_str
                _logger.info(f"  Result: {log_result}")

                # Track page creation
                if fn_name == "write_wiki_page":
                    pages_created += 1
                    filename = result.get("filename", "?")
                    if on_progress:
                        on_progress({
                            "event": "page_created",
                            "filename": filename,
                            "pages_created": pages_created,
                        })

                if fn_name == "mark_file_ingested":
                    marked = result.get("marked", "?")
                    _logger.info(f"  Marked ingested: {marked}")
                    if on_progress:
                        on_progress({
                            "event": "file_ingested",
                            "filename": marked,
                        })

                # Build tool result message
                tool_result_messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str,
                })

            # Append assistant message then tool results
            messages.append(assistant_msg)
            messages.extend(tool_result_messages)

            round_num += 1
            continue

        # No tool calls — model is done
        final_content = msg.content or ""
        _logger.info(
            f"LLM completed after {round_num + 1} rounds, "
            f"{total_prompt_tokens + total_completion_tokens} total tokens"
        )
        break

    # Check if we exceeded max rounds
    if round_num >= MAX_TOOL_ROUNDS:
        _logger.warning(f"Hit MAX_TOOL_ROUNDS ({MAX_TOOL_ROUNDS}) — ingest incomplete")
        status = "max_rounds_exceeded"

    total_tokens = total_prompt_tokens + total_completion_tokens
    _logger.info(
        f"Ingest done: {pages_created} pages, {total_tokens} tokens, model={final_model}, status={status}"
    )

    return {
        "content": final_content,
        "model": final_model,
        "pages_created": pages_created,
        "tokens_used": total_tokens,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_ingest(subject: str, model: str = None, on_progress: callable = None) -> dict:
    """Run the full ingest workflow for a subject.

    Args:
        subject: Subject name (e.g., 'comunicacion-digital').
        model: Model name. Defaults to AVAILABLE_MODELS[0] if None.
        on_progress: Optional callback(event_dict) for progress tracking.
            Event dicts have an 'event' key:
            - {"event": "start", "pending": N}
            - {"event": "page_created", "filename": str, "pages_created": N}
            - {"event": "file_ingested", "filename": str}
            - {"event": "complete", "result": dict}

    Returns:
        dict with keys: pages_created, tokens_used, model, status, message, finished_at
    """
    model = model or AVAILABLE_MODELS[0]
    start_time = time.time()

    _logger.info(f"=" * 60)
    _logger.info(f"Ingest START for subject='{subject}', model='{model}'")

    try:
        # 1. Find un-ingested files
        uningested = _get_uningested_files(subject)
        if not uningested:
            _logger.info(f"No un-ingested files for '{subject}' — nothing to do")
            result = {
                "pages_created": 0,
                "tokens_used": 0,
                "model": "no-op",
                "status": "complete",
                "message": "No new files to ingest",
                "finished_at": _now_iso(),
            }
            if on_progress:
                on_progress({"event": "complete", "result": result})
            return result

        _logger.info(f"Found {len(uningested)} un-ingested file(s): {', '.join(uningested)}")

        if on_progress:
            on_progress({"event": "start", "pending": len(uningested)})

        # 2. Build prompt
        prompt = _build_ingest_prompt(subject, uningested)

        # 3. Read SCHEMA.md for system context
        schema_path = os.path.join(VAULT_DIR, "subjects", subject, "SCHEMA.md")
        schema_context = ""
        if os.path.isfile(schema_path):
            try:
                with open(schema_path, encoding="utf-8") as f:
                    schema_context = f.read()
                _logger.info(f"Loaded SCHEMA.md ({len(schema_context)} chars)")
            except OSError as e:
                _logger.warning(f"Could not read SCHEMA.md: {e}")

        # 4. Build messages
        system_content = (
            f"You are a wiki ingest assistant for subject '{subject}'.\n"
            f"The vault is at vaults/subjects/{subject}/.\n"
            f"You have read_vault_file, write_wiki_page, and mark_file_ingested tools.\n"
            f"Be thorough, create high-quality pages, and always call mark_file_ingested after each file is done."
        )
        if schema_context:
            system_content += f"\n\n## SCHEMA.md\n\n{schema_context}"

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]

        # 5. Run the tool loop
        _logger.info(f"Starting LLM tool loop with model='{model}'")
        loop_result = _run_tool_loop(messages, subject, model, on_progress)

        elapsed = time.time() - start_time
        status = loop_result.get("status", "error")
        is_error = status.startswith("error") or status == "max_rounds_exceeded"
        result_status = "error" if is_error else "complete"

        message = (
            f"LLM ingest {'error' if is_error else 'complete'}: "
            f"{loop_result['pages_created']} pages created, "
            f"{loop_result['tokens_used']} tokens used, "
            f"in {elapsed:.0f}s"
        )
        if is_error:
            message += f" ({status})"

        result = {
            "pages_created": loop_result["pages_created"],
            "tokens_used": loop_result["tokens_used"],
            "model": loop_result["model"],
            "status": result_status,
            "message": message,
            "finished_at": _now_iso(),
            "elapsed_seconds": int(elapsed),
        }

        _logger.info(message)
        _logger.info(f"Ingest FINISHED for '{subject}' — status={result_status}")

        if on_progress:
            on_progress({"event": "complete", "result": result})

        return result

    except Exception as e:
        elapsed = time.time() - start_time
        _logger.error(f"Ingest FAILED for '{subject}' after {elapsed:.0f}s: {e}")
        _logger.debug(traceback.format_exc())

        result = {
            "pages_created": 0,
            "tokens_used": 0,
            "model": model or "unknown",
            "status": "error",
            "message": f"Ingest failed: {e}",
            "finished_at": _now_iso(),
            "elapsed_seconds": int(elapsed),
        }

        if on_progress:
            on_progress({"event": "complete", "result": result})

        return result
