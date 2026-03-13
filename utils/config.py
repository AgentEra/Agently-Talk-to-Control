from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any, Callable

import yaml
from agently import Agently


ENV_PATTERN = re.compile(r"\$\{ENV\.([A-Za-z_][A-Za-z0-9_]*)\}")
AGENT_MANAGED_KEYS = {
    "AGENT_SETTINGS",
    "MODEL_CLIENT",
    "MODEL_URL",
    "MODEL_AUTH",
    "MODEL_OPTIONS",
    "PROXY",
}


def _load_dotenv_near_settings(path: str | Path) -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    settings_path = Path(path).resolve()
    for directory in (settings_path.parent, *settings_path.parent.parents):
        dotenv_path = directory / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path, override=False)
            return


def _read_env(name: str) -> str:
    if name not in os.environ:
        raise KeyError(f"Environment variable '{name}' is required by SETTINGS.yaml but is not set.")
    return os.environ[name]


def _coerce_yaml_scalar(value: str) -> Any:
    try:
        return yaml.safe_load(value)
    except Exception:
        return value


def _resolve_env_string(value: str) -> Any:
    matches = list(ENV_PATTERN.finditer(value))
    if not matches:
        return value

    if len(matches) == 1 and matches[0].span() == (0, len(value)):
        return _coerce_yaml_scalar(_read_env(matches[0].group(1)))

    resolved = value
    for match in matches:
        env_name = match.group(1)
        resolved = resolved.replace(match.group(0), _read_env(env_name))
    return resolved


def _resolve_env_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_values(item) for item in value]
    if isinstance(value, str):
        return _resolve_env_string(value)
    return value


def _resolve_project_side_settings(data: dict[str, Any]) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in data.items():
        if key in AGENT_MANAGED_KEYS:
            resolved[key] = value
        else:
            resolved[key] = _resolve_env_values(value)
    return resolved


def load_settings(path: str | Path) -> dict[str, Any]:
    _load_dotenv_near_settings(path)
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise TypeError("SETTINGS.yaml must contain a dictionary at the top level.")
    resolved = _resolve_project_side_settings(data)
    if not isinstance(resolved, dict):
        raise TypeError("Resolved SETTINGS.yaml must still be a dictionary.")
    return resolved


def _normalize_model_url(url: str) -> dict[str, str]:
    suffixes = ("/chat/completions", "/completions", "/embeddings")
    if any(url.endswith(suffix) for suffix in suffixes):
        return {"full_url": url}
    return {"base_url": url}


def resolve_agent_settings(settings: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    new_settings = settings.get("AGENT_SETTINGS", {})
    if isinstance(new_settings, dict) and new_settings:
        provider = str(new_settings.get("provider", "OpenAICompatible"))
        options = copy.deepcopy(new_settings.get("options", {}))
        if not isinstance(options, dict):
            raise TypeError("AGENT_SETTINGS.options must be a dictionary.")
        if settings.get("PROXY") and "proxy" not in options:
            options["proxy"] = settings["PROXY"]
        return provider, options

    provider = str(settings.get("MODEL_CLIENT") or "OpenAICompatible")
    options: dict[str, Any] = {}
    model_url = settings.get("MODEL_URL")
    if model_url:
        options.update(_normalize_model_url(str(model_url)))
    if settings.get("MODEL_AUTH"):
        options["auth"] = copy.deepcopy(settings["MODEL_AUTH"])
    if settings.get("MODEL_OPTIONS"):
        options.update(copy.deepcopy(settings["MODEL_OPTIONS"]))
    if settings.get("PROXY"):
        options["proxy"] = settings["PROXY"]
    return provider, options


def create_agent_factory(settings: dict[str, Any]) -> Callable[[], Any]:
    provider, provider_settings = resolve_agent_settings(settings)
    debug_enabled = bool(settings.get("DEBUG"))

    def factory():
        agent = Agently.create_agent()
        agent.set_settings(provider, copy.deepcopy(provider_settings), auto_load_env=True)
        agent.set_settings("debug", debug_enabled)
        return agent

    return factory
