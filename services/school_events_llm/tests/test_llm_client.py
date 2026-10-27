"""Проверка HTTP-клиента на поддельном OpenAI-совместимом сервере (как LM Studio)."""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from app.llm.client import LLMError, OpenAICompatibleClient, build_client
from app.settings import Settings


class FakeLMStudio(BaseHTTPRequestHandler):
    models = ["qwen3.5-9b"]
    reject_schema = True
    bodies: list = []

    def log_message(self, *args):
        """Выполняет операцию `log_message`, реализующую соответствующую часть логики текущего модуля.

        Параметры:
            `*args`.
        """
        pass

    def _send(self, code, payload):
        """Выполняет внутреннюю служебную операцию `_send` в рамках текущего модуля.

        Параметры:
            `code`, `payload`.
        """
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        """Выполняет операцию `do_GET`, реализующую соответствующую часть логики текущего модуля.
        """
        if self.path == "/v1/models":
            self._send(200, {"data": [{"id": m} for m in self.models]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        """Выполняет операцию `do_POST`, реализующую соответствующую часть логики текущего модуля.
        """
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeLMStudio.bodies.append(body)
        if body.get("response_format", {}).get("type") == "json_schema" and self.reject_schema:
            self._send(400, {"error": "json_schema is not supported"})
            return
        self._send(200, {"choices": [{"message": {"content": '<think>план</think>{"ok": true}'}}],
                         "usage": {"prompt_tokens": 10, "completion_tokens": 3}})


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Выполняет операцию `setUpClass`, реализующую соответствующую часть логики текущего модуля.
        """
        cls.server = HTTPServer(("127.0.0.1", 0), FakeLMStudio)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/v1"
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        """Выполняет операцию `tearDownClass`, реализующую соответствующую часть логики текущего модуля.
        """
        cls.server.shutdown()
        cls.tmp.cleanup()

    def client(self, **cfg):
        """Создаёт тестовый LLM-клиент с заданной конфигурацией.

        Параметры:
            `**cfg`.
        """
        lock = {"path": Path(self.tmp.name) / "lm.lock", "wait_seconds": 5, "enabled": True}
        base = {"provider": "openai_compatible", "base_url": self.base, "model_id": "auto_loaded", "timeout_seconds": 10,
                "structured_output_mode": "auto", "reasoning_mode": "disabled", "local": True}
        base.update(cfg)
        return OpenAICompatibleClient("qwen_local_9b", base, None, lock)

    def test_auto_loaded_and_schema_fallback(self):
        """Проверяет сценарий теста: auto loaded and schema fallback."""
        FakeLMStudio.bodies.clear()
        c = self.client()
        res = c.generate(messages=[{"role": "user", "content": "hi"}], task_name="t", output_schema={"type": "object", "properties": {}},
                         max_tokens=50, temperature=0.1)
        self.assertEqual(res.provider_model_id, "qwen3.5-9b")
        self.assertEqual(res.text, '{"ok": true}')
        self.assertTrue(res.reasoning_stripped)
        self.assertEqual(res.structured_mode, "none")
        self.assertEqual(len(FakeLMStudio.bodies), 2)
        self.assertEqual(FakeLMStudio.bodies[0]["response_format"]["type"], "json_schema")
        self.assertNotIn("response_format", FakeLMStudio.bodies[1])
        res2 = c.generate(messages=[{"role": "user", "content": "hi"}], task_name="t", output_schema={"type": "object"},
                          max_tokens=50, temperature=0.1)
        self.assertEqual(len(FakeLMStudio.bodies), 3)  # схема больше не пробуется
        self.assertEqual(res2.usage["completion_tokens"], 3)

    def test_no_think_tag_option(self):
        """Проверяет сценарий теста: no think tag option."""
        FakeLMStudio.bodies.clear()
        self.client(thinking_method=None, disable_thinking_method="no_think_tag", structured_output_mode="none").generate(
            messages=[{"role": "user", "content": "привет"}], task_name="t", output_schema=None, max_tokens=5, temperature=0)
        self.assertTrue(FakeLMStudio.bodies[0]["messages"][-1]["content"].endswith("/no_think"))

    def test_ambiguous_models(self):
        """Проверяет сценарий теста: ambiguous models."""
        FakeLMStudio.models = ["a", "b"]
        try:
            with self.assertRaises(LLMError) as ctx:
                self.client().model_id()
            self.assertEqual(ctx.exception.code, "MODEL_UNAVAILABLE")
        finally:
            FakeLMStudio.models = ["qwen3.5-9b"]

    def test_strict_schema_keeps_title_fields(self):
        """Проверяет сценарий теста: strict schema keeps title fields."""
        from app.contracts.llm import VariantPackage
        from app.llm.client import strict_schema
        schema = strict_schema(VariantPackage.model_json_schema())
        self.assertIn("title", schema["$defs"]["VariantBody"]["properties"])
        self.assertIn("title", schema["$defs"]["Block"]["properties"])
        self.assertFalse(schema["$defs"]["Block"]["additionalProperties"])
        self.assertNotIn("title", schema["$defs"]["Block"])  # служебная подпись удалена

    def test_gateway_profile_uses_environment_only(self):
        """Проверяет, что адрес и ключ командного шлюза берутся только из ENV."""
        config_path = Path(__file__).resolve().parents[1] / "config" / "models.json"
        models = json.loads(config_path.read_text(encoding="utf-8"))["models"]
        gateway = models["urfu_qwen_27b"]
        self.assertIsNone(gateway["base_url"])
        self.assertEqual(gateway["base_url_env"], "LITELLM_BASE_URL")
        self.assertEqual(gateway["api_key_env"], "LITELLM_API_KEY")
        self.assertNotIn("api_key", gateway)
        self.assertTrue(gateway["enabled"])

    def test_gateway_base_url_and_key_can_come_from_environment(self):
        """Проверяет конфигурацию OpenAI-compatible шлюза через имена ENV-переменных."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "models.json").write_text(
                json.dumps({
                    "default_model": "gateway",
                    "models": {
                        "gateway": {
                            "provider": "openai_compatible",
                            "base_url": None,
                            "base_url_env": "TEST_GATEWAY_URL",
                            "model_id": "qwen3.5-9b",
                            "api_key_env": "TEST_GATEWAY_KEY",
                            "timeout_seconds": 10,
                            "structured_output_mode": "none",
                            "reasoning_mode": "disabled",
                            "local": False,
                            "enabled": True,
                        }
                    },
                }),
                encoding="utf-8",
            )
            settings = Settings(
                root=root,
                env={
                    "TEST_GATEWAY_URL": self.base,
                    "TEST_GATEWAY_KEY": "secret-test-key",
                },
            )
            client = build_client(settings)
            self.assertEqual(client.base_url, self.base)
            self.assertEqual(client.api_key, "secret-test-key")
            self.assertEqual(client.model_id(), "qwen3.5-9b")

    def test_t020_unavailable(self):
        """Проверяет сценарий теста: t020 unavailable."""
        c = OpenAICompatibleClient("x", {"base_url": "http://127.0.0.1:9/v1", "model_id": "m", "timeout_seconds": 10, "local": True}, None, None)
        with self.assertRaises(LLMError) as ctx:
            c.generate(messages=[{"role": "user", "content": "x"}], task_name="t", output_schema=None, max_tokens=5, temperature=0)
        self.assertEqual(ctx.exception.code, "MODEL_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()