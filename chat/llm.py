"""LLM streaming loop — the core generator for multi-round tool calling."""

import json
import os
import time
import uuid
from collections import namedtuple

from openai import OpenAI

from .types import NIM_BASE_URL, MAX_TOOL_ROUNDS
from .tools import get_tool_definitions, execute_tool

ToolCall = namedtuple("ToolCall", ["index", "id", "name", "arguments"], defaults=[0, "", "", ""])

_client = None


def get_llm_client():
    """Create a cached OpenAI client for NVIDIA NIM endpoint."""
    global _client
    if _client is not None:
        return _client

    # Resolve API key
    api_key = os.environ.get("NIM_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        # Try config.yaml
        import yaml
        cfg_path = os.path.expanduser("~/study/config.yaml")
        if os.path.isfile(cfg_path):
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            api_key = cfg.get("nim_api_key", cfg.get("nim_base_url", ""))

    _client = OpenAI(
        base_url=NIM_BASE_URL,
        api_key=api_key,
        timeout=900,
        max_retries=2,
    )
    return _client


def get_extra_body(model):
    """Get extra body params for the NIM API call."""
    if "deepseek-v4" in model.lower() or "deepseek" in model.lower():
        return {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}}
    return {}


def stream_chat(messages, model, subject):
    """Multi-round tool-calling generator. Yields event dicts."""
    client = get_llm_client()
    round_num = 0
    current_messages = list(messages)

    while round_num < MAX_TOOL_ROUNDS:
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=current_messages,
                tools=get_tool_definitions(),
                tool_choice="auto",
                stream=True,
                extra_body=get_extra_body(model),
                temperature=1,
                top_p=0.95,
                max_tokens=16384,
            )
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
                # Handle both standard (tc_chunk.function.name) and non-standard (tc_chunk.name) formats
                chunk_id = tc_chunk.id or ""
                chunk_name = ""
                chunk_args = ""
                if hasattr(tc_chunk, 'function') and tc_chunk.function:
                    chunk_name = tc_chunk.function.name or ""
                    chunk_args = tc_chunk.function.arguments or ""
                else:
                    # Non-standard: name/arguments at top level
                    chunk_name = getattr(tc_chunk, 'name', '') or ""
                    chunk_args = getattr(tc_chunk, 'arguments', '') or ""
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
            # Build assistant message with tool calls
            sorted_calls = sorted(tool_calls_buffer.values(), key=lambda x: x.index)
            # Ensure every tool call has a valid id (some models don't provide one)
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

            # Execute each tool and append results
            for tc in sorted_calls:
                yield {"type": "tool_call", "name": tc.name, "arguments": tc.arguments}
                result = execute_tool(subject, tc.name, tc.arguments)
                result_str = json.dumps(result)
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str
                })
                yield {"type": "tool_result", "name": tc.name, "result": result}

            round_num += 1
            continue

        # Fallback: finish_reason == "tool_calls" but buffer is empty or tool names missing
        # This happens with some NIM-wrapped models that return tool calls differently.
        # Treat the content as a regular response and stop.
        if finish_reason == "tool_calls":
            # Log the problem — the model said it wanted tool calls but didn't provide them.
            # Just yield what we have as text content and stop.
            import sys
            print(f"[DEBUG] tool_calls_buffer: {tool_calls_buffer}", file=sys.stderr)
            print(f"[DEBUG] full_content: {repr(full_content)}", file=sys.stderr)
            if full_content:
                yield {"type": "token", "content": full_content}

        # finish_reason is stop, length, or no tool calls
        break

    yield {"type": "done", "model": model, "content": full_content, "reasoning": full_reasoning}
