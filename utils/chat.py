from __future__ import annotations

from typing import Any


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
    return str(value)


def gradio_history_to_chat_history(history: list[Any] | None) -> list[dict[str, str]]:
    chat_history: list[dict[str, str]] = []

    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role")
            content = _to_text(item.get("content"))
            if role in ("user", "assistant") and content:
                chat_history.append({"role": role, "content": content})
            continue

        if isinstance(item, (list, tuple)) and len(item) == 2:
            user_message, assistant_message = item
            user_text = _to_text(user_message)
            assistant_text = _to_text(assistant_message)
            if user_text:
                chat_history.append({"role": "user", "content": user_text})
            if assistant_text:
                chat_history.append({"role": "assistant", "content": assistant_text})

    return chat_history
