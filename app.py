from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import gradio as gr

from controllers import create_controller_info
from utils.chat import gradio_history_to_chat_history
from utils.config import create_agent_factory, load_settings
from workflows.talk_to_control import build_flow


ROOT = Path(__file__).resolve().parent
SETTINGS = load_settings(ROOT / "SETTINGS.yaml")

logging.basicConfig(
    level=logging.DEBUG if SETTINGS.get("DEBUG") else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOGGER = logging.getLogger("agently-talk-to-control")

controller_info, controller_desc_info = create_controller_info(SETTINGS["CONTROLLERS"])
agent_factory = create_agent_factory(SETTINGS)
flow = build_flow(
    initial_status=SETTINGS["INITIAL_STATUS"],
    controller_info=controller_info,
    controller_desc_info=controller_desc_info,
    agent_factory=agent_factory,
    logger=LOGGER,
)


def chat(message: str, history: list[Any]):
    execution = flow.create_execution()
    transcript = ""
    payload = {
        "message": str(message or "").strip(),
        "chat_history": gradio_history_to_chat_history(history),
    }

    try:
        stream = execution.get_runtime_stream(initial_value=payload)
        for item in stream:
            if isinstance(item, dict) and item.get("type") == "append":
                transcript += str(item.get("text", ""))
                yield transcript
        result = execution.get_result(timeout=5)
        if isinstance(result, dict):
            final_text = str(result.get("transcript", transcript))
        else:
            final_text = str(result or transcript)
        if final_text and final_text != transcript:
            yield final_text
    except Exception as exc:
        LOGGER.exception("Request failed")
        yield f"[Error]: {exc}"


demo = gr.ChatInterface(
    fn=chat,
    title="Agently Talk to Control (v4)",
    description="Natural language control workflow rebuilt with Agently v4 TriggerFlow.",
)


if __name__ == "__main__":
    launch_kwargs = SETTINGS.get("UI", {})
    demo.launch(**launch_kwargs)
