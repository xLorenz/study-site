"""LLM streaming loop — the core generator for multi-round tool calling."""

import json
import os
import time
import uuid
from collections import namedtuple

from openai import OpenAI, RateLimitError

from .types import (
    NIM_BASE_URL,
    ZEN_BASE_URL,
    ZEN_API_KEY_ENV,
    PROVIDER_FOR_MODEL,
    MAX_TOOL_ROUNDS,
)
from .tools import get_tool_definitions, execute_tool

ToolCall = namedtuple("ToolCall", ["index", "id", "name", "arguments"], defaults=[0, "", "", ""])

_nvidia_client = None
_zen_client = None


def _resolve_api_key(provider):
    """Resolve API key for a provider from env or config.yaml."""
    study_dir = os.environ.get("STUDY_DIR", os.path.expanduser("~/study"))
    cfg_path = os.path.join(study_dir, "config.yaml")
    
    if provider == "zen":
        api_key = os.environ.get(ZEN_API_KEY_ENV, "")
    else:
        api_key = os.environ.get("NIM_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")
        if api_key:
            return api_key
        # NVIDIA fallback: try config.yaml
        import yaml
        if os.path.isfile(cfg_path):
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            api_key = cfg.get("nim_api_key", "")
        return api_key

    if not api_key:
        # Try config.yaml for Zen key too
        import yaml
        if os.path.isfile(cfg_path):
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            api_key = cfg.get("opencode_zen_api_key", "")
    return api_key


def get_llm_client(provider="nvidia"):
    """Create a cached OpenAI client for the specified provider."""
    global _nvidia_client, _zen_client

    if provider == "zen":
        if _zen_client is not None:
            return _zen_client
        api_key = _resolve_api_key("zen")
        if not api_key:
            raise ValueError(
                "OpenCode Zen API key not found. "
                f"Set {ZEN_API_KEY_ENV} env var or add 'opencode_zen_api_key' to config.yaml"
            )
        _zen_client = OpenAI(
            base_url=ZEN_BASE_URL,
            api_key=api_key,
            timeout=900,
            max_retries=0,  # we handle retries ourselves
        )
        return _zen_client

    # Default: NVIDIA
    if _nvidia_client is not None:
        return _nvidia_client

    api_key = _resolve_api_key("nvidia")
    if not api_key:
        raise ValueError("NVIDIA API key not found. Set NIM_API_KEY or NVIDIA_API_KEY.")

    _nvidia_client = OpenAI(
        base_url=NIM_BASE_URL,
        api_key=api_key,
        timeout=900,
        max_retries=2,
    )
    return _nvidia_client


def get_extra_body(model, provider="nvidia"):
    """Get extra body params for the API call.

    NVIDIA's DeepSeek V4 supports chat_template_kwargs for thinking/reasoning.
    OpenCode Zen may not support this — skip for Zen provider.
    """
    if provider == "nvidia" and ("deepseek" in model.lower()):
        return {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}}
    return {}


def _is_429_error(e):
    """Check if an exception is a 429 rate-limit error."""
    if isinstance(e, RateLimitError):
        return True
    status = getattr(e, "status_code", 0) or getattr(e, "code", 0)
    return status == 429


def _api_call_with_retry(client, model, messages, tools, extra_body, max_retries=3):
    """Call the LLM API with retry logic for transient errors (5xx, timeouts).

    Does NOT retry on 429 (rate-limit) — the caller should handle provider fallback.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
                extra_body=extra_body,
                temperature=1,
                top_p=0.95,
                max_tokens=16384,
            )
        except Exception as e:
            last_exception = e
            # Don't retry 429 — caller handles fallback
            if _is_429_error(e):
                raise
            status = getattr(e, "status_code", 0) or getattr(e, "code", 0)
            is_timeout = status == 0 or "timeout" in str(e).lower() or "504" in str(e)
            if (status >= 500 or is_timeout) and attempt < max_retries - 1:
                time.sleep(1 * (2 ** attempt))
                continue
            break
    raise last_exception


def _try_model_round(models_to_try, current_messages, tools, extra_body_func, subject):
    """Try API call across a list of (provider, model) pairs for fallback.

    Returns (stream, provider_used, model_used) on success.
    Raises the last exception if all providers fail.
    """
    last_exception = None
    for provider, model in models_to_try:
        try:
            client = get_llm_client(provider)
            extra_body = extra_body_func(model, provider)
            stream = _api_call_with_retry(client, model, current_messages, tools, extra_body)
            return stream, provider, model
        except Exception as e:
            last_exception = e
            # Only fall back if this is a connection/rate-limit error on the primary
            if not _is_429_error(e) and not "timeout" in str(e).lower():
                # Non-rate-limit, non-timeout error — don't waste time falling back
                raise
            # Otherwise continue to next provider in list
            continue
    raise last_exception


def stream_chat(messages, model, subject):
    """Multi-round tool-calling generator. Yields event dicts.

    Tries the requested model first (determines provider from PROVIDER_FOR_MODEL).
    If it's a Zen model and rate-limited, falls back to NVIDIA.
    """
    # Determine primary provider and build fallback list
    primary_provider = PROVIDER_FOR_MODEL.get(model, "nvidia")
    fallback_model = None
    fallback_provider = None

    if primary_provider == "zen":
        # Full fallback chain: Zen → NVIDIA v4-pro → v4-flash → glm-5.1
        models_to_try = [
            ("zen", model),
            ("nvidia", "deepseek-ai/deepseek-v4-pro"),
            ("nvidia", "deepseek-ai/deepseek-v4-flash"),
            ("nvidia", "z-ai/glm-5.1"),
        ]
    else:
        # NVIDIA model — just use it directly
        models_to_try = [
            ("nvidia", model),
        ]

    round_num = 0
    current_messages = list(messages)
    tools_executed = False
    skip_rounds = 0

    while round_num < MAX_TOOL_ROUNDS:
        try:
            stream, actual_provider, actual_model = _try_model_round(
                models_to_try, current_messages,
                get_tool_definitions(), get_extra_body, subject
            )
            # Remember which model/provider we're actually using for tool calls
            current_model = actual_model
        except Exception as e:
            yield {"type": "error", "message": f"LLM API error: {e}"}
            return

        # Phase 1: Accumulate stream
        tool_calls_buffer = {}
        full_content = ""
        full_reasoning = ""
        finish_reason = None

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                full_content += delta.content
                yield {"type": "token", "content": delta.content}

            # Reasoning content (DeepSeek V4 specific)
            reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
            if reasoning:
                full_reasoning += reasoning
                yield {"type": "reasoning", "content": reasoning}

            # Tool calls accumulator
            for tc_chunk in (delta.tool_calls or []):
                idx = tc_chunk.index
                if idx not in tool_calls_buffer:
                    tool_calls_buffer[idx] = ToolCall(index=idx)
                buf = tool_calls_buffer[idx]
                chunk_id = tc_chunk.id or ""
                chunk_name = ""
                chunk_args = ""
                if hasattr(tc_chunk, "function") and tc_chunk.function:
                    chunk_name = tc_chunk.function.name or ""
                    chunk_args = tc_chunk.function.arguments or ""
                else:
                    chunk_name = getattr(tc_chunk, "name", "") or ""
                    chunk_args = getattr(tc_chunk, "arguments", "") or ""
                if chunk_id:
                    buf = buf._replace(id=buf.id + chunk_id)
                if chunk_name:
                    buf = buf._replace(name=buf.name + chunk_name)
                if chunk_args:
                    buf = buf._replace(arguments=buf.arguments + chunk_args)
                tool_calls_buffer[idx] = buf

            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason

        if finish_reason == "tool_calls" and tool_calls_buffer:
            sorted_calls = sorted(tool_calls_buffer.values(), key=lambda x: x.index)
            for i, tc in enumerate(sorted_calls):
                if not tc.id or not tc.id.strip():
                    sorted_calls[i] = tc._replace(id=f"tc_{uuid.uuid4().hex[:8]}")
            assistant_msg = {
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments}
                    }
                    for tc in sorted_calls
                ]
            }
            current_messages.append(assistant_msg)

            for tc in sorted_calls:
                yield {"type": "tool_call", "id": tc.id, "name": tc.name, "arguments": tc.arguments}
                result = execute_tool(subject, tc.name, tc.arguments)
                result_str = json.dumps(result)
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str
                })
                yield {"type": "tool_result", "name": tc.name, "result": result}

            round_num += 1
            tools_executed = True
            continue

        # If we just executed tools, continue even if finish_reason is "stop" or "length"
        if tools_executed:
            tools_executed = False
            skip_rounds += 1
            if skip_rounds > 5:
                break
            if full_content:
                current_messages.append({"role": "assistant", "content": full_content})
            continue

        if finish_reason == "tool_calls":
            import sys
            print(f"[DEBUG] tool_calls_buffer: {tool_calls_buffer}", file=sys.stderr)
            print(f"[DEBUG] full_content: {repr(full_content)}", file=sys.stderr)
            if full_content:
                yield {"type": "token", "content": full_content}

        break

    if not full_content and full_reasoning:
        full_content = f"(Modelo solo produjo razonamiento — {len(full_reasoning)} caracteres sin respuesta visible)"

    yield {"type": "done", "model": current_model, "content": full_content, "reasoning": full_reasoning}
