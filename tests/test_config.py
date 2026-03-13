from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.config import load_settings, resolve_agent_settings


class ConfigEnvTests(unittest.TestCase):
    def test_load_settings_keeps_agent_settings_raw_and_resolves_project_fields(self):
        yaml_text = textwrap.dedent(
            """
            AGENT_SETTINGS:
              options:
                base_url: ${ENV.TEST_BASE_URL}
                model: ${ENV.TEST_MODEL}
            UI:
              server_port: ${ENV.TEST_PORT}
              server_name: "http://${ENV.TEST_HOST}:${ENV.TEST_PORT}"
            """
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.yaml"
            path.write_text(yaml_text, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "TEST_BASE_URL": "https://example.com/v1",
                    "TEST_MODEL": "demo-model",
                    "TEST_PORT": "7860",
                    "TEST_HOST": "127.0.0.1",
                },
                clear=False,
            ):
                settings = load_settings(path)

        self.assertEqual(settings["AGENT_SETTINGS"]["options"]["base_url"], "${ENV.TEST_BASE_URL}")
        self.assertEqual(settings["AGENT_SETTINGS"]["options"]["model"], "${ENV.TEST_MODEL}")
        self.assertEqual(settings["UI"]["server_port"], 7860)
        self.assertEqual(settings["UI"]["server_name"], "http://127.0.0.1:7860")

    def test_load_settings_raises_for_missing_project_env(self):
        yaml_text = "UI:\n  server_port: ${ENV.MISSING_ENV_NAME}\n"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.yaml"
            path.write_text(yaml_text, encoding="utf-8")

            with self.assertRaises(KeyError):
                load_settings(path)

    def test_load_settings_reads_parent_dotenv_for_project_fields(self):
        yaml_text = textwrap.dedent(
            """
            UI:
              server_port: ${ENV.TEST_PARENT_PORT}
            """
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_dir = root / "project"
            project_dir.mkdir()
            (root / ".env").write_text(
                "\n".join(
                    [
                        "TEST_PARENT_PORT=7860",
                    ]
                ),
                encoding="utf-8",
            )
            settings_path = project_dir / "settings.yaml"
            settings_path.write_text(yaml_text, encoding="utf-8")

            with patch.dict(
                os.environ,
                {},
                clear=True,
            ):
                settings = load_settings(settings_path)

        self.assertEqual(settings["UI"]["server_port"], 7860)

    def test_resolve_agent_settings_keeps_env_placeholders_for_agently(self):
        settings = {
            "AGENT_SETTINGS": {
                "provider": "OpenAICompatible",
                "options": {
                    "base_url": "${ENV.TEST_BASE_URL}",
                    "model": "${ENV.TEST_MODEL}",
                    "auth": {
                        "api_key": "${ENV.TEST_API_KEY}",
                    },
                },
            }
        }

        provider, options = resolve_agent_settings(settings)
        self.assertEqual(provider, "OpenAICompatible")
        self.assertEqual(options["base_url"], "${ENV.TEST_BASE_URL}")
        self.assertEqual(options["model"], "${ENV.TEST_MODEL}")
        self.assertEqual(options["auth"]["api_key"], "${ENV.TEST_API_KEY}")
