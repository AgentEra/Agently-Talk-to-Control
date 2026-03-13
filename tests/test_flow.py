from __future__ import annotations

import asyncio
import time
import unittest

from workflows.talk_to_control import build_flow, replace_placeholders


def turn_on_camera(camera_name):
    return {"camera_name": camera_name, "power": 1}


class TriggerFlowTests(unittest.TestCase):
    def setUp(self):
        self.initial_status = {
            "camera_status": {
                "camera_1": {"power": 1, "zoom_factor": 1.0},
                "camera_2": {"power": 0, "zoom_factor": 1.0},
            }
        }
        self.controller_info = {
            "turn_on_camera": {
                "desc": "turn on the camera",
                "args": {"camera_name": ("'camera_1' | 'camera_2'", "[Required]")},
                "func": turn_on_camera,
                "get": ["camera_status"],
                "set": {"camera_status.<$camera_name>.power": "<$power>"},
            }
        }
        self.controller_desc_info = {
            "turn_on_camera": {
                "desc": "turn on the camera",
                "args": ["camera_name"],
            }
        }

    def _run_flow(self, flow, message="test request"):
        execution = flow.create_execution()
        runtime_stream = execution.get_runtime_stream(
            initial_value={"message": message, "chat_history": []}
        )
        transcript = ""
        for item in runtime_stream:
            if isinstance(item, dict) and item.get("type") == "append":
                transcript += str(item.get("text", ""))
        result = execution.get_result(timeout=5)
        return transcript, result

    def test_replace_placeholders_keeps_native_type_for_single_placeholder(self):
        value = replace_placeholders("<$power>", {"power": 1})
        self.assertEqual(value, 1)

    def test_direct_reply_flow(self):
        def plan_request(message, chat_history, status, controller_desc_info):
            return {
                "can_reply_directly": True,
                "direct_reply": "camera_1 is on",
                "action_plan": [],
                "can_not_do": "",
            }

        flow = build_flow(
            initial_status=self.initial_status,
            controller_info=self.controller_info,
            controller_desc_info=self.controller_desc_info,
            agent_factory=lambda: None,
            plan_request=plan_request,
            action_request=lambda action, env_info, controller_args: {},
        )
        transcript, result = self._run_flow(flow)
        self.assertIn("[Direct Reply]: camera_1 is on", transcript)
        self.assertFalse(result["blocked"])
        self.assertEqual(result["status"]["camera_status"]["camera_2"]["power"], 0)

    def test_action_flow_updates_status(self):
        def plan_request(message, chat_history, status, controller_desc_info):
            return {
                "can_reply_directly": False,
                "direct_reply": "",
                "action_plan": [
                    {
                        "purpose": "turn on camera_2",
                        "key_factors": ["camera_2"],
                        "op_name": "turn_on_camera",
                    }
                ],
                "can_not_do": "",
            }

        def action_request(action, env_info, controller_args):
            return {
                "can_do": True,
                "explanation": "",
                "suggestion_order": "",
                "args": {"camera_name": "camera_2"},
            }

        flow = build_flow(
            initial_status=self.initial_status,
            controller_info=self.controller_info,
            controller_desc_info=self.controller_desc_info,
            agent_factory=lambda: None,
            plan_request=plan_request,
            action_request=action_request,
        )
        transcript, result = self._run_flow(flow)
        self.assertIn("[Operation]: turn on camera_2", transcript)
        self.assertIn("camera_status.camera_2.power = 1", transcript)
        self.assertEqual(result["status"]["camera_status"]["camera_2"]["power"], 1)
        self.assertEqual(len(result["completed_actions"]), 1)

    def test_plan_args_skip_action_request(self):
        def plan_request(message, chat_history, status, controller_desc_info):
            return {
                "can_reply_directly": False,
                "direct_reply": "",
                "action_plan": [
                    {
                        "purpose": "turn on camera_2",
                        "key_factors": ["camera_2"],
                        "op_name": "turn_on_camera",
                        "args": {"camera_name": "camera_2"},
                    }
                ],
                "can_not_do": "",
            }

        def action_request(*args, **kwargs):
            raise AssertionError("action_request should not be called when plan already provides valid args")

        flow = build_flow(
            initial_status=self.initial_status,
            controller_info=self.controller_info,
            controller_desc_info=self.controller_desc_info,
            agent_factory=lambda: None,
            plan_request=plan_request,
            action_request=action_request,
        )
        transcript, result = self._run_flow(flow)
        self.assertIn("camera_status.camera_2.power = 1", transcript)
        self.assertEqual(result["status"]["camera_status"]["camera_2"]["power"], 1)

    def test_independent_actions_run_in_parallel_stage(self):
        start_times = []

        async def async_turn_on_camera(camera_name):
            start_times.append((camera_name, time.perf_counter()))
            await asyncio.sleep(0.15)
            return {"camera_name": camera_name, "power": 1}

        controller_info = {
            "turn_on_camera": {
                "desc": "turn on the camera",
                "args": {"camera_name": ("'camera_1' | 'camera_2'", "[Required]")},
                "func": async_turn_on_camera,
                "get": ["camera_status"],
                "set": {"camera_status.<$camera_name>.power": "<$power>"},
            }
        }

        def plan_request(message, chat_history, status, controller_desc_info):
            return {
                "can_reply_directly": False,
                "direct_reply": "",
                "action_plan": [
                    {
                        "purpose": "turn on camera_1",
                        "key_factors": ["camera_1"],
                        "op_name": "turn_on_camera",
                        "args": {"camera_name": "camera_1"},
                    },
                    {
                        "purpose": "turn on camera_2",
                        "key_factors": ["camera_2"],
                        "op_name": "turn_on_camera",
                        "args": {"camera_name": "camera_2"},
                    },
                ],
                "can_not_do": "",
            }

        flow = build_flow(
            initial_status=self.initial_status,
            controller_info=controller_info,
            controller_desc_info=self.controller_desc_info,
            agent_factory=lambda: None,
            plan_request=plan_request,
            action_request=lambda action, env_info, controller_args: {},
        )

        started_at = time.perf_counter()
        transcript, result = self._run_flow(flow)
        elapsed = time.perf_counter() - started_at

        self.assertEqual(len(start_times), 2)
        self.assertLess(abs(start_times[0][1] - start_times[1][1]), 0.08)
        self.assertLess(elapsed, 0.28)
        self.assertIn("[Parallel Stage]: executed 2 actions", transcript)
        self.assertEqual(result["status"]["camera_status"]["camera_1"]["power"], 1)
        self.assertEqual(result["status"]["camera_status"]["camera_2"]["power"], 1)
        self.assertEqual(len(result["completed_actions"]), 2)


if __name__ == "__main__":
    unittest.main()
