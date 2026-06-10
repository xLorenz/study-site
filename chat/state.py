"""Conversation persistence and background task manager."""

import json
import os
import threading
import traceback
import uuid
from queue import Queue

from .types import CHATS_DIR, MAX_HISTORY_MESSAGES


_background_tasks = {}  # task_id -> TaskInfo


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


def save_chat(subject, messages):
    """Save chat history to disk, trimmed to MAX_HISTORY_MESSAGES."""
    path = os.path.join(CHATS_DIR, f"{subject}.json")
    # Keep only user and assistant messages, trimmed
    # Preserve tool_calls data on assistant messages
    trimmed = []
    for m in messages:
        if m["role"] == "assistant":
            entry = {"role": "assistant", "content": m["content"]}
            if "tool_calls" in m and m["tool_calls"]:
                entry["tool_calls"] = m["tool_calls"]
            trimmed.append(entry)
        elif m["role"] == "user":
            trimmed.append({"role": "user", "content": m["content"]})
    if len(trimmed) > MAX_HISTORY_MESSAGES:
        trimmed = trimmed[-MAX_HISTORY_MESSAGES:]
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"messages": trimmed}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving chat for {subject}: {e}")


def start_background_task(subject, user_message, conversation, model):
    """Spawn a daemon thread running stream_chat(). Returns task_id."""
    task_id = uuid.uuid4().hex[:8]
    task = TaskInfo(subject, model)
    _background_tasks[task_id] = task

    thread = threading.Thread(
        target=_run_task,
        args=(task_id, task, subject, user_message, list(conversation), model),
        daemon=True
    )
    thread.start()
    return task_id


def _normalize_conversation(conversation):
    """Normalize tool_calls in conversation messages to the OpenAI API format."""
    normalized = []
    for msg in conversation:
        entry = {"role": msg["role"], "content": msg.get("content", "")}
        if msg["role"] == "assistant" and "tool_calls" in msg and msg["tool_calls"]:
            normalized_tcs = []
            for tc in msg["tool_calls"]:
                if isinstance(tc, dict):
                    tc_id = tc.get("id") or f"tc_{uuid.uuid4().hex[:8]}"
                    # Handle both stored format {name, arguments} and OpenAI format {id, type, function}
                    fn = tc.get("function", {})
                    tc_name = tc.get("name", fn.get("name", "unknown"))
                    raw_args = tc.get("arguments", fn.get("arguments", "{}"))
                    if isinstance(raw_args, dict):
                        raw_args = json.dumps(raw_args)
                    normalized_tcs.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {"name": tc_name, "arguments": raw_args}
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
                    "name": event.get("name", ""),
                    "arguments": event.get("arguments", "{}"),
                    "label": _tool_label(event.get("name", ""), event.get("arguments", "{}"))
                })
            if event["type"] == "tool_result":
                for te in tool_events:
                    if te["name"] == event.get("name") and "result" not in te:
                        te["result"] = event.get("result")
                        break

        # Save to chat history
        history = list(conversation)
        history.append({"role": "user", "content": user_message})
        asst_msg = {"role": "assistant", "content": assistant_content}
        if tool_events:
            asst_msg["tool_calls"] = tool_events
        history.append(asst_msg)
        save_chat(subject, history)

    except Exception as e:
        task.buffer.put({"type": "error", "message": str(e)})
        traceback.print_exc()
    finally:
        task.buffer.put({"type": "_task_done"})
        task.done.set()
        # Clean up after 60s
        threading.Timer(60, lambda: _background_tasks.pop(task_id, None)).start()


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
    return name


def get_task(task_id):
    """Get a background task by ID."""
    return _background_tasks.get(task_id)