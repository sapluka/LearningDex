import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx
from litellm.llms.custom_httpx.http_handler import HTTPHandler

from app import agents


class TestVisionRequest(unittest.TestCase):
    def test_deepseek_anthropic_receives_top_level_thinking_flag(self):
        bodies = []
        def respond(client, url, **kwargs):
            bodies.append(json.loads(kwargs["data"]))
            return httpx.Response(200, request=httpx.Request("POST", url), json={
                "id": "test", "type": "message", "role": "assistant", "model": "deepseek-v4-flash",
                "content": [{"type": "text", "text": '{"valid":true,"reason":"清晰"}'}],
                "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 12},
            })
        with tempfile.TemporaryDirectory() as root:
            frame = Path(root) / "frame.jpg"
            frame.write_bytes(b"image")
            trace = {}
            with mock.patch.object(HTTPHandler, "post", respond):
                self.assertTrue(agents.validate_frame({"protocol": "anthropic",
                    "base_url": "https://api.deepseek.com/anthropic", "model": "deepseek-v4-flash",
                    "api_key": "unit-test"}, str(frame), details=trace))
        self.assertEqual(len(bodies), 1)
        self.assertEqual(bodies[0]["thinking"], {"type": "disabled"})
        self.assertNotIn("extra_body", bodies[0])
        self.assertNotIn("allowed_openai_params", bodies[0])
        self.assertEqual(trace["finish_reason"], "stop")

    def test_deepseek_openai_keeps_sdk_extra_body(self):
        with tempfile.TemporaryDirectory() as root:
            frame = Path(root) / "frame.jpg"
            frame.write_bytes(b"image")
            with mock.patch.object(agents.llm, "text", return_value='{"valid":true}') as request:
                agents.validate_frame({"protocol": "openai", "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-flash"}, str(frame))
        self.assertEqual(request.call_args.kwargs["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertNotIn("thinking", request.call_args.kwargs)
