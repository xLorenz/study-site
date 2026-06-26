"""Conversation persistence and background task manager."""

import json
import os
import threading
import traceback
import uuid
from queue import Queue

from .types import CHATS_DIR, MAX_HISTORY_MESSAGES


_background_tasks = {}  # task_id -> TaskInfo
_tasks_lock = threading.Lock()


class TaskInfo:
    def __init__(self, subject, model):
        self.subject = subject
        self.model = model
        self.buffer = Queue()
        self.done = threading.Event()
        self.messages = []


def load_chat(subject):
    """Load chat history from disk."""
    path = os.path.join(CHATS_DIR, f"{subject}.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("messages", [])
    except (json.JSONDecodeError, Exception):
        return []


_chat_save_lock = threading.Lock()

def save_chat(subject, messages):
    """Save chat history to disk, trimmed to MAX_HISTORY_MESSAGES.

    Tool calls are stored WITHOUT their 'result' fields to keep history
    lightweight — results bloat the file to 100K+ with wiki content that
    gets resent on every retry, causing 400 BadRequest from the LLM API.
    """
    path = os.path.join(CHATS_DIR, f"{subject}.json")
    trimmed = []
    for m in messages:
        if m["role"] == "assistant":
            entry = {"role": "assistant", "content": m["content"]}
            if "tool_calls" in m and m["tool_calls"]:
                trimmed_tcs = []
                for tc in m["tool_calls"]:
                    clean = {k: v for k, v in tc.items() if k != "result"}
                    trimmed_tcs.append(clean)
                entry["tool_calls"] = trimmed_tcs
            trimmed.append(entry)
        elif m["role"] == "tool":
            trimmed.append({k: v for k, v in m.items() if k != "result"})
        elif m["role"] == "user":
            trimmed.append({"role": "user", "content": m["content"]})
    if len(trimmed) > MAX_HISTORY_MESSAGES:
        trimmed = trimmed[-MAX_HISTORY_MESSAGES:]
    try:
        with _chat_save_lock:
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"messages": trimmed}, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
    except Exception as e:
        print(f"Error saving chat for {subject}: {e}")


def delete_chat_file(subject):
    """Delete the chat history file for a subject."""
    path = os.path.join(CHATS_DIR, f"{subject}.json")
    try:
        with _chat_save_lock:
            if os.path.isfile(path):
                os.remove(path)
                return True
            return False
    except Exception as e:
        print(f"Error deleting chat for {subject}: {e}")
        return False


def start_background_task(subject, user_message, conversation, model):
    """Spawn a daemon thread running stream_chat(). Returns task_id."""
    task_id = uuid.uuid4().hex[:8]
    task = TaskInfo(subject, model)
    with _tasks_lock:
        _background_tasks[task_id] = task

    thread = threading.Thread(
        target=_run_task,
        args=(task_id, task, subject, user_message, list(conversation), model),
        daemon=True
    )
    thread.start()
    return task_id


def _normalize_conversation(conversation):
    """Normalize tool_calls in conversation messages to the OpenAI API format.

    Extracts tool results stored inside assistant message tool_calls into
    proper ``role: "tool"`` messages with matching ``tool_call_id``.
    This is required by the OpenAI-compatible NIM API — without it the
    API returns ``400 Unterminated string`` because it expects tool messages
    alongside assistant tool_call messages.
    """
    # First pass: collect tool message IDs so we can match them to assistant
    # tool_calls (saved history has no 'id' on assistant tool_calls, but
    # the following tool messages keep their original tool_call_id).
    tool_message_ids = []
    for msg in conversation:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            tool_message_ids.append(msg["tool_call_id"])

    normalized = []
    tool_id_idx = 0
    for msg in conversation:
        entry = {"role": msg["role"], "content": msg.get("content", "")}
        if msg["role"] == "assistant" and "tool_calls" in msg and msg["tool_calls"]:
            # Check if any tool_call has a result (embedded) — if none do AND
            # there are no following tool messages, these are stale/orphaned
            # tool_calls from a frontend that doesn't store role:"tool" messages.
            # Strip them to avoid sending orphaned tool_calls to the LLM API.
            has_any_result = any(
                tc.get("result") is not None
                for tc in msg["tool_calls"]
                if isinstance(tc, dict)
            )
            if not has_any_result and not tool_message_ids:
                # Stale tool_calls with no results and no tool messages — strip them
                normalized.append(entry)
                continue

            normalized_tcs = []
            for tc in msg["tool_calls"]:
                if isinstance(tc, dict):
                    fn = tc.get("function", {})
                    tc_name = tc.get("name", fn.get("name", "unknown"))
                    raw_args = tc.get("arguments", fn.get("arguments", "{}"))
                    if isinstance(raw_args, dict):
                        raw_args = json.dumps(raw_args)

                    # Use saved ID, or match by position to tool messages, or generate
                    tc_id = tc.get("id")
                    if not tc_id:
                        if tool_id_idx < len(tool_message_ids):
                            tc_id = tool_message_ids[tool_id_idx]
                        else:
                            tc_id = f"tc_{uuid.uuid4().hex[:8]}"
                    tool_id_idx += 1

                    normalized_tcs.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {"name": tc_name, "arguments": raw_args}
                    })
                    # If this tool call has a result, emit a role:tool message right after
                    result = tc.get("result")
                    if result is not None:
                        result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        normalized.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": result_str
                        })
            if normalized_tcs:
                entry["tool_calls"] = normalized_tcs
        normalized.append(entry)
    return normalized


def _run_task(task_id, task, subject, user_message, conversation, model):
    """Run the full stream_chat generator, writing events to task.buffer."""
    from .prompt import build_chat_system_prompt
    from .llm import stream_chat

    try:
        system_prompt = build_chat_system_prompt(subject)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(_normalize_conversation(conversation))
        messages.append({"role": "user", "content": user_message})

        assistant_content = ""
        tool_events = []  # collect tool_call/tool_result events for persistence
        for event in stream_chat(messages, task.model, task.subject):
            task.buffer.put(event)
            if event["type"] == "done":
                assistant_content = event.get("content", "")
            if event["type"] == "tool_call":
                tool_events.append({
                    "id": event.get("id", ""),
                    "name": event.get("name", ""),
                    "arguments": event.get("arguments", "{}"),
                    "label": _tool_label(event.get("name", ""), event.get("arguments", "{}"))
                })
            if event["type"] == "tool_result":
                for te in tool_events:
                    if te["name"] == event.get("name") and "result" not in te:
                        te["result"] = event.get("result")
                        break

        # Save to chat history (clean: strip stale tool_calls from incoming conversation)
        history = _normalize_conversation(conversation)
        # Remove any tool messages from history that came from normalization —
        # save_chat will regenerate them properly from the stream's tool_events.
        # We only keep user and assistant messages from the normalized conversation.
        cleaned = [m for m in history if m["role"] in ("user", "assistant")]
        cleaned.append({"role": "user", "content": user_message})
        asst_msg = {"role": "assistant", "content": assistant_content}
        if tool_events:
            asst_msg["tool_calls"] = tool_events
        cleaned.append(asst_msg)
        save_chat(subject, cleaned)

    except Exception as e:
        task.buffer.put({"type": "error", "message": str(e)})
        traceback.print_exc()
    finally:
        task.buffer.put({"type": "_task_done"})
        task.done.set()
        # Clean up after 60s
        def _cleanup(tid=task_id):
            with _tasks_lock:
                _background_tasks.pop(tid, None)
        threading.Timer(60, _cleanup).start()


def _tool_label(name, arguments_raw):
    """Extract a short label from tool name + arguments."""
    try:
        args = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
    except (json.JSONDecodeError, TypeError):
        args = {}
    if name == "read_vault_file":
        return args.get("path", "file")
    elif name == "write_study_object":
        return args.get("filename", "object")
    elif name == "write_study_video":
        return args.get("filename", "video")
    elif name == "highlight_node":
        nodes = args.get("nodes", [])
        return ", ".join(nodes) if nodes else "nodes"
    return name


def get_task(task_id):
    """Get a background task by ID."""
    with _tasks_lock:
        return _background_tasks.get(task_id)