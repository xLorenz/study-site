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
    trimmed = [m for m in messages if m["role"] in ("user", "assistant")]
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


def _run_task(task_id, task, subject, user_message, conversation, model):
    """Run the full stream_chat generator, writing events to task.buffer."""
    from .prompt import build_chat_system_prompt
    from .llm import stream_chat

    try:
        system_prompt = build_chat_system_prompt(subject)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation)
        messages.append({"role": "user", "content": user_message})

        assistant_content = ""
        for event in stream_chat(messages, task.model, task.subject):
            task.buffer.put(event)
            if event["type"] == "done":
                assistant_content = event.get("content", "")

        # Save to chat history
        history = list(conversation)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_content})
        save_chat(subject, history)

    except Exception as e:
        task.buffer.put({"type": "error", "message": str(e)})
        traceback.print_exc()
    finally:
        task.buffer.put({"type": "_task_done"})
        task.done.set()
        # Clean up after 60s
        threading.Timer(60, lambda: _background_tasks.pop(task_id, None)).start()


def get_task(task_id):
    """Get a background task by ID."""
    return _background_tasks.get(task_id)
