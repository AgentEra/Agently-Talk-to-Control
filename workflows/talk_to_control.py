from __future__ import annotations

import asyncio
import copy
import logging
import re
import time
from typing import Any, Callable

from agently import TriggerFlow, TriggerFlowRuntimeData


PlannerFn = Callable[[str, list[dict[str, str]], dict[str, Any], dict[str, Any]], dict[str, Any]]
ActionPlannerFn = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]
PLAN_ENSURE_KEYS = [
    "can_reply_directly",
    "direct_reply",
    "action_plan",
    "can_not_do",
]
ACTION_ENSURE_KEYS = [
    "can_do",
    "explanation",
    "suggestion_order",
    "args",
]


def replace_placeholders(origin_value: Any, key_values: dict[str, Any]) -> Any:
    if not isinstance(origin_value, str):
        return origin_value

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = key_values.get(key, match.group(0))
        return str(value)

    pattern = r"<\$(\w+)>"
    if origin_value.startswith("<$") and origin_value.endswith(">"):
        return key_values.get(origin_value[2:-1], origin_value)
    return re.sub(pattern, replace, origin_value)


def get_nested_value(data: dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def set_nested_value(data: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def create_plan_model_request(
    agent: Any,
    message: str,
    chat_history: list[dict[str, str]],
    status: dict[str, Any],
    controller_desc_info: dict[str, Any],
):
    if chat_history:
        agent.set_chat_history(chat_history)

    return (
        agent.input(message)
        .info(
            {
                "current_equipment_status": status,
                "operation_dict": controller_desc_info,
                "operation_names": list(controller_desc_info.keys()),
            }
        )
        .instruct(
            [
                "Decide whether the user can be answered directly from the current equipment status.",
                "If actions are needed, split the request into ordered controller actions.",
                "Each action can reference one controller only.",
                "Only use operation names from {info.operation_names}.",
                "If the request cannot be completed, explain why in the same language as the user message.",
            ]
        )
        .output(
            {
                "can_reply_directly": (bool, "Whether the request can be answered directly from the current status."),
                "direct_reply": (
                    str,
                    "If can_reply_directly is true, give the direct answer. Otherwise return an empty string.",
                ),
                "action_plan": (
                    [
                        {
                            "purpose": (str, "One clear action purpose derived from the user message."),
                            "key_factors": [(str, "Key factor needed to execute this action.")],
                            "op_name": (
                                str,
                                "One operation name. Must be from {info.operation_names}.",
                            ),
                            "args": (
                                "dict",
                                "Try to directly generate controller arguments for this operation. If not sure, return an empty object.",
                            ),
                        }
                    ],
                    "If direct reply is false, build an ordered action plan. Otherwise return [].",
                ),
                "can_not_do": (
                    str,
                    "If the request cannot be completed, explain why. Otherwise return an empty string.",
                ),
            }
        )
    )


def create_action_model_request(
    agent: Any,
    action: dict[str, Any],
    env_info: dict[str, Any],
    controller_args: dict[str, Any],
):
    return (
        agent.input(
            {
                "purpose": action.get("purpose", ""),
                "key_factors": action.get("key_factors", []),
            }
        )
        .info(
            {
                "environment": env_info,
                "controller_args": controller_args,
            }
        )
        .instruct(
            [
                "Generate controller calling arguments for the purpose in {input}.",
                "Only use keys defined in {info.controller_args}.",
                "If the action cannot be executed safely or correctly, set can_do to false.",
                "When can_do is false, explanation and suggestion_order must use the same language as the user's purpose.",
            ]
        )
        .output(
            {
                "can_do": (bool, "Whether the controller call can be executed."),
                "explanation": (
                    str,
                    "If can_do is false, explain why. Otherwise return an empty string.",
                ),
                "suggestion_order": (
                    str,
                    "If can_do is false, give the user a natural language suggestion. Otherwise return an empty string.",
                ),
                "args": (
                    controller_args,
                    "If can_do is true, generate the controller arguments. Otherwise return an empty object.",
                ),
            }
        )
    )


def _extract_list_index(path: str) -> int | None:
    match = re.search(r"\[(\d+)\]", path)
    if match:
        return int(match.group(1))
    return None


def _is_required_arg(arg_desc: str) -> bool:
    return "[Required]" in str(arg_desc)


def _parse_enum_choices(type_spec: str) -> list[str]:
    choices = []
    for part in str(type_spec).split("|"):
        item = part.strip()
        if len(item) >= 2 and item[0] == "'" and item[-1] == "'":
            choices.append(item[1:-1])
        else:
            return []
    return choices


def coerce_arg_value(value: Any, type_spec: str) -> Any:
    enum_choices = _parse_enum_choices(type_spec)
    if enum_choices:
        normalized = str(value)
        if normalized not in enum_choices:
            raise ValueError(f"value '{normalized}' not in enum choices")
        return normalized

    normalized_type = str(type_spec).strip().lower()
    if normalized_type == "int":
        if isinstance(value, bool):
            raise ValueError("bool is not accepted as int")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return int(str(value).strip())
    if normalized_type == "float":
        if isinstance(value, bool):
            raise ValueError("bool is not accepted as float")
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value).strip())
    if normalized_type == "bool":
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in ("true", "1", "yes", "on"):
            return True
        if normalized in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"value '{value}' can not be coerced to bool")
    return value


def normalize_action_args(raw_args: Any, controller_config: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw_args, dict):
        return None

    normalized: dict[str, Any] = {}
    for arg_name, arg_config in controller_config.get("args", {}).items():
        type_spec = arg_config[0] if isinstance(arg_config, tuple) and len(arg_config) > 0 else ""
        arg_desc = arg_config[1] if isinstance(arg_config, tuple) and len(arg_config) > 1 else ""
        if arg_name not in raw_args:
            if _is_required_arg(arg_desc):
                return None
            continue
        try:
            normalized[arg_name] = coerce_arg_value(raw_args[arg_name], str(type_spec))
        except Exception:
            return None
    return normalized


def build_update_items(set_mapping: dict[str, Any], key_values: dict[str, Any]) -> list[tuple[str, Any]]:
    updates: list[tuple[str, Any]] = []
    for origin_key, origin_value in set_mapping.items():
        target_key = str(replace_placeholders(origin_key, key_values))
        target_value = replace_placeholders(origin_value, key_values)
        updates.append((target_key, target_value))
    return updates


def apply_update_items(status: dict[str, Any], updates: list[tuple[str, Any]]) -> None:
    for target_key, target_value in updates:
        set_nested_value(status, target_key, target_value)


def infer_action_resource_keys(action: dict[str, Any], controller_config: dict[str, Any]) -> set[str]:
    args = action.get("resolved_args") or action.get("args") or {}
    if not isinstance(args, dict) or not args:
        return set()

    resource_keys: set[str] = set()
    for origin_key in controller_config.get("set", {}).keys():
        target_key = str(replace_placeholders(origin_key, args))
        if "<$" in target_key:
            return set()
        parts = [part for part in target_key.split(".") if part]
        if not parts:
            continue
        resource_key = ".".join(parts[:-1]) if len(parts) > 1 else parts[0]
        resource_keys.add(resource_key)

    return resource_keys


def build_action_stages(action_plan: list[dict[str, Any]], controller_info: dict[str, Any]) -> list[list[int]]:
    stages: list[list[int]] = []
    current_stage: list[int] = []
    current_resources: set[str] = set()
    current_stage_is_serial = False

    for index, action in enumerate(action_plan):
        op_name = str(action.get("op_name", ""))
        controller_config = controller_info.get(op_name)
        if controller_config is None:
            action_resources = set()
        else:
            action_resources = infer_action_resource_keys(action, controller_config)

        should_serialize = not action_resources
        if not current_stage:
            current_stage = [index]
            current_resources = set(action_resources)
            current_stage_is_serial = should_serialize
            stages.append(current_stage)
            continue

        if should_serialize or current_stage_is_serial or current_resources.intersection(action_resources):
            current_stage = [index]
            current_resources = set(action_resources)
            current_stage_is_serial = should_serialize
            stages.append(current_stage)
            continue

        current_stage.append(index)
        current_resources.update(action_resources)

    return stages


def build_plan_request(agent_factory: Callable[[], Any]) -> PlannerFn:
    def plan_request(
        message: str,
        chat_history: list[dict[str, str]],
        status: dict[str, Any],
        controller_desc_info: dict[str, Any],
    ) -> dict[str, Any]:
        agent = agent_factory()
        return create_plan_model_request(
            agent,
            message,
            chat_history,
            status,
            controller_desc_info,
        ).start(
            ensure_keys=PLAN_ENSURE_KEYS,
            key_style="dot",
            raise_ensure_failure=False,
        )

    return plan_request


def build_action_request(agent_factory: Callable[[], Any]) -> ActionPlannerFn:
    def action_request(
        action: dict[str, Any],
        env_info: dict[str, Any],
        controller_args: dict[str, Any],
    ) -> dict[str, Any]:
        agent = agent_factory()
        return create_action_model_request(
            agent,
            action,
            env_info,
            controller_args,
        ).start(
            ensure_keys=ACTION_ENSURE_KEYS,
            key_style="dot",
            raise_ensure_failure=False,
        )

    return action_request


async def maybe_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


async def append_transcript(data: TriggerFlowRuntimeData, text: str) -> None:
    transcript = str(data.state.get("transcript") or "")
    transcript += text
    data.state.set("transcript", transcript)
    await data.async_put({"type": "append", "text": text})


def collect_env_info(status: dict[str, Any], controller_config: dict[str, Any]) -> dict[str, Any]:
    env_info = {}
    for key in controller_config.get("get", []):
        env_info[key] = copy.deepcopy(get_nested_value(status, key))
    return env_info


def apply_status_updates(
    status: dict[str, Any],
    set_mapping: dict[str, Any],
    key_values: dict[str, Any],
) -> list[tuple[str, Any]]:
    updates: list[tuple[str, Any]] = []
    for origin_key, origin_value in set_mapping.items():
        target_key = str(replace_placeholders(origin_key, key_values))
        target_value = replace_placeholders(origin_value, key_values)
        set_nested_value(status, target_key, target_value)
        updates.append((target_key, target_value))
    return updates


def build_flow(
    *,
    initial_status: dict[str, Any],
    controller_info: dict[str, Any],
    controller_desc_info: dict[str, Any],
    agent_factory: Callable[[], Any],
    logger: logging.Logger | None = None,
    plan_request: PlannerFn | None = None,
    action_request: ActionPlannerFn | None = None,
) -> TriggerFlow:
    flow = TriggerFlow(name="talk-to-control-v4")
    planner = plan_request or build_plan_request(agent_factory)
    action_planner = action_request or build_action_request(agent_factory)
    active_logger = logger or logging.getLogger("talk-to-control-v4")

    async def prepare_request(data: TriggerFlowRuntimeData):
        message = str((data.value or {}).get("message", "")).strip()
        chat_history = list((data.value or {}).get("chat_history", []))
        data.state.set("message", message)
        data.state.set("chat_history", chat_history)
        data.state.set("status", copy.deepcopy(initial_status))
        data.state.set("transcript", "")
        data.state.set("action_plan", [])
        data.state.set("completed_actions", [])
        data.state.set("blocked_explanation", "")
        data.state.set("blocked_suggestion", "")
        data.state.set("direct_reply_streamed", False)
        data.state.set("blocked_explanation_streamed", False)
        data.state.set("blocked_suggestion_streamed", False)
        data.state.set("plan_previews", [])
        data.state.set("action_stages", [])
        return message

    async def make_operation_plan_streaming(data: TriggerFlowRuntimeData) -> dict[str, Any]:
        message = str(data.state.get("message") or "")
        status = copy.deepcopy(data.state.get("status") or {})
        chat_history = list(data.state.get("chat_history") or [])
        agent = agent_factory()
        request = create_plan_model_request(
            agent,
            message,
            chat_history,
            status,
            controller_desc_info,
        )
        response = request.get_response()

        can_reply_directly = False
        direct_reply_started = False
        previewed_indexes: set[int] = set()
        preview_stream_started: set[int] = set()

        async for stream in response.get_async_generator(type="instant"):
            if stream.wildcard_path == "can_reply_directly" and stream.is_complete:
                can_reply_directly = bool(stream.value)
                if can_reply_directly and not direct_reply_started:
                    await append_transcript(data, "[Direct Reply]: ")
                    data.state.set("direct_reply_streamed", True)
                    direct_reply_started = True
                continue

            if can_reply_directly and stream.wildcard_path == "direct_reply":
                if stream.delta:
                    await append_transcript(data, stream.delta)
                continue

            if stream.wildcard_path == "action_plan[*].purpose":
                item_index = _extract_list_index(stream.path)
                if item_index is None:
                    continue
                if stream.delta:
                    if item_index not in preview_stream_started:
                        preview_stream_started.add(item_index)
                        await append_transcript(data, "[Plan]: ")
                    await append_transcript(data, stream.delta)
                if stream.is_complete and item_index not in previewed_indexes:
                    previewed_indexes.add(item_index)
                    previews = list(data.state.get("plan_previews") or [])
                    previews.append(str(stream.value))
                    data.state.set("plan_previews", previews)
                    if item_index in preview_stream_started:
                        await append_transcript(data, "\n")
                    else:
                        await append_transcript(data, f"[Plan]: {stream.value}\n")

        result = await response.result.async_get_data(
            ensure_keys=PLAN_ENSURE_KEYS,
            key_style="dot",
            raise_ensure_failure=False,
        )
        if result.get("can_reply_directly") and data.state.get("direct_reply_streamed"):
            await append_transcript(data, "\n\n")
        return result

    async def make_action_request_streaming(
        data: TriggerFlowRuntimeData,
        action: dict[str, Any],
        env_info: dict[str, Any],
        controller_args: dict[str, Any],
    ) -> dict[str, Any]:
        agent = agent_factory()
        request = create_action_model_request(
            agent,
            action,
            env_info,
            controller_args,
        )
        response = request.get_response()

        can_do = True
        explanation_started = False
        suggestion_started = False

        async for stream in response.get_async_generator(type="instant"):
            if stream.wildcard_path == "can_do" and stream.is_complete:
                can_do = bool(stream.value)
                continue

            if not can_do and stream.wildcard_path == "explanation":
                if stream.delta and not explanation_started:
                    await append_transcript(data, "[Can Not Apply]: ")
                    data.state.set("blocked_explanation_streamed", True)
                    explanation_started = True
                if stream.delta:
                    await append_transcript(data, stream.delta)
                continue

            if not can_do and stream.wildcard_path == "suggestion_order":
                if stream.delta and not suggestion_started:
                    if explanation_started:
                        await append_transcript(data, "\n\n")
                    await append_transcript(data, "[Suggestion]: ")
                    data.state.set("blocked_suggestion_streamed", True)
                    suggestion_started = True
                if stream.delta:
                    await append_transcript(data, stream.delta)

        result = await response.result.async_get_data(
            ensure_keys=ACTION_ENSURE_KEYS,
            key_style="dot",
            raise_ensure_failure=False,
        )
        if result.get("can_do") is False:
            if explanation_started and not suggestion_started:
                await append_transcript(data, "\n\n")
            if suggestion_started:
                await append_transcript(data, "\n\n")
        return result

    async def make_operation_plan(data: TriggerFlowRuntimeData):
        message = str(data.state.get("message") or "")
        if not message:
            await data.async_emit("CannotDo", "Please enter a request first.")
            return {"halt": True}

        status = copy.deepcopy(data.state.get("status") or {})
        chat_history = list(data.state.get("chat_history") or [])
        try:
            if plan_request is None:
                return await make_operation_plan_streaming(data)
            return await maybe_call(
                planner,
                message,
                chat_history,
                status,
                controller_desc_info,
            )
        except Exception as exc:
            active_logger.exception("Failed to build operation plan")
            await data.async_emit("CannotDo", f"Planning failed: {exc}")
            return {"halt": True}

    async def route_plan(data: TriggerFlowRuntimeData):
        plan = data.value or {}
        if plan.get("halt"):
            return plan
        if plan.get("can_reply_directly") and plan.get("direct_reply"):
            await data.async_emit("DirectReply", str(plan["direct_reply"]))
            return plan
        if plan.get("can_not_do"):
            await data.async_emit("CannotDo", str(plan["can_not_do"]))
            return plan

        action_plan = list(plan.get("action_plan") or [])
        for action in action_plan:
            action["resolved_args"] = None
            op_name = str(action.get("op_name", ""))
            controller_config = controller_info.get(op_name)
            if controller_config is not None:
                action["resolved_args"] = normalize_action_args(
                    action.get("args") or {},
                    controller_config,
                )
        data.state.set("action_plan", action_plan)
        if not action_plan:
            await data.async_emit("CannotDo", "No valid action plan could be generated for this request.")
            return plan

        action_stages = build_action_stages(action_plan, controller_info)
        data.state.set("action_stages", action_stages)
        await data.async_emit("RunActionStage", {"stage_index": 0})
        return plan

    async def handle_direct_reply(data: TriggerFlowRuntimeData):
        if not data.state.get("direct_reply_streamed"):
            await append_transcript(data, f"[Direct Reply]: {data.value}\n\n")
        await data.async_emit("Finalize", {"blocked": False})
        return data.value

    async def handle_cannot_do(data: TriggerFlowRuntimeData):
        await append_transcript(data, f"[Can Not Apply]: {data.value}\n\n")
        data.state.set("blocked_explanation", str(data.value))
        await data.async_emit("Finalize", {"blocked": True})
        return data.value

    async def execute_single_action(
        data: TriggerFlowRuntimeData,
        action: dict[str, Any],
        base_status: dict[str, Any],
        *,
        allow_streaming_fallback: bool,
    ) -> dict[str, Any]:
        op_name = str(action.get("op_name", ""))
        controller_config = controller_info.get(op_name)
        if controller_config is None:
            return {
                "blocked": True,
                "explanation": f"Unknown operation: {op_name}",
                "suggestion": "",
                "updates": [],
                "completed_action": None,
            }

        args = action.get("resolved_args")
        env_info = collect_env_info(base_status, controller_config)

        if not isinstance(args, dict):
            try:
                if action_request is None and allow_streaming_fallback:
                    calling_info = await make_action_request_streaming(
                        data,
                        action,
                        env_info,
                        controller_config.get("args", {}),
                    )
                else:
                    calling_info = await maybe_call(
                        action_planner,
                        action,
                        env_info,
                        controller_config.get("args", {}),
                    )
            except Exception as exc:
                active_logger.exception("Failed to generate controller arguments")
                return {
                    "blocked": True,
                    "explanation": f"Argument planning failed: {exc}",
                    "suggestion": "",
                    "updates": [],
                    "completed_action": None,
                }

            if not calling_info.get("can_do"):
                return {
                    "blocked": True,
                    "explanation": str(calling_info.get("explanation") or "The action can not be executed."),
                    "suggestion": str(calling_info.get("suggestion_order") or ""),
                    "updates": [],
                    "completed_action": None,
                }

            args = normalize_action_args(
                calling_info.get("args") or {},
                controller_config,
            )
            if args is None:
                return {
                    "blocked": True,
                    "explanation": "The generated controller arguments are incomplete or invalid.",
                    "suggestion": "",
                    "updates": [],
                    "completed_action": None,
                }

        result = await maybe_call(controller_config["func"], **dict(args))
        result_dict = result if isinstance(result, dict) else {"result": result}
        key_values = {**dict(args), **result_dict}
        updates = build_update_items(
            controller_config.get("set", {}),
            key_values,
        )

        return {
            "blocked": False,
            "explanation": "",
            "suggestion": "",
            "updates": updates,
            "completed_action": {
                "op_name": op_name,
                "args": dict(args),
                "result": result_dict,
            },
        }

    async def run_action_stage(data: TriggerFlowRuntimeData):
        payload = data.value or {}
        stage_index = int(payload.get("stage_index", 0))
        action_stages = list(data.state.get("action_stages") or [])
        actions = list(data.state.get("action_plan") or [])
        if stage_index >= len(action_stages):
            await data.async_emit("Finalize", {"blocked": False})
            return {"status": "completed"}

        stage_action_indexes = list(action_stages[stage_index])
        stage_actions = [actions[index] for index in stage_action_indexes]
        base_status = copy.deepcopy(data.state.get("status") or {})

        for action in stage_actions:
            await append_transcript(data, f"[Operation]: {action.get('purpose', action.get('op_name', 'operation'))}\n\n")

        started_at = time.perf_counter()
        results = await asyncio.gather(
            *[
                execute_single_action(
                    data,
                    action,
                    base_status,
                    allow_streaming_fallback=len(stage_actions) == 1,
                )
                for action in stage_actions
            ]
        )
        elapsed = time.perf_counter() - started_at
        if len(stage_actions) > 1:
            await append_transcript(
                data,
                f"[Parallel Stage]: executed {len(stage_actions)} actions in {elapsed:.2f}s\n\n",
            )

        current_status = copy.deepcopy(data.state.get("status") or {})
        completed_actions = list(data.state.get("completed_actions") or [])
        first_blocked: dict[str, Any] | None = None

        for result in results:
            if result.get("blocked"):
                if first_blocked is None:
                    first_blocked = result
                continue

            updates = list(result.get("updates") or [])
            apply_update_items(current_status, updates)
            completed_action = result.get("completed_action")
            if completed_action:
                completed_actions.append(completed_action)
            for target_key, target_value in updates:
                await append_transcript(data, f"[Operation Result]: {target_key} = {target_value}\n\n")

        data.state.set("status", current_status)
        data.state.set("completed_actions", completed_actions)

        if first_blocked is not None:
            data.state.set("blocked_explanation", str(first_blocked.get("explanation") or ""))
            data.state.set("blocked_suggestion", str(first_blocked.get("suggestion") or ""))
            await data.async_emit("Finalize", {"blocked": True})
            return {"status": "blocked"}

        await data.async_emit("RunActionStage", {"stage_index": stage_index + 1})
        return {"status": "next"}

    async def finalize(data: TriggerFlowRuntimeData):
        explanation = str(data.state.get("blocked_explanation") or "")
        suggestion = str(data.state.get("blocked_suggestion") or "")
        transcript = str(data.state.get("transcript") or "")
        blocked = bool((data.value or {}).get("blocked"))

        if blocked:
            if explanation and not data.state.get("blocked_explanation_streamed"):
                await append_transcript(data, f"[Can Not Apply]: {explanation}\n\n")
            if suggestion and not data.state.get("blocked_suggestion_streamed"):
                await append_transcript(data, f"[Suggestion]: {suggestion}\n\n")

        result = {
            "transcript": str(data.state.get("transcript") or ""),
            "status": copy.deepcopy(data.state.get("status") or {}),
            "completed_actions": copy.deepcopy(data.state.get("completed_actions") or []),
            "blocked": blocked,
        }
        data.set_result(result)
        await data.async_stop_stream()
        return result

    flow.to(prepare_request).to(make_operation_plan).to(route_plan).end()
    flow.when("DirectReply").to(handle_direct_reply)
    flow.when("CannotDo").to(handle_cannot_do)
    flow.when("RunActionStage").to(run_action_stage)
    flow.when("Finalize").to(finalize).end()
    return flow
