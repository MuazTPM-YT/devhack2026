import json
import os
import tempfile
import unittest
from unittest import mock

from brain import llm

SCHEMA = {"type": "object", "properties": {"confidence": {"type": "number"}}, "required": ["confidence"]}
KEY = "sk-test-not-real"


def validate(args):
    if not isinstance(args.get("confidence"), (int, float)):
        raise ValueError("bad diagnosis")
    return args


def reply(args, tokens=(100, 20)):
    return {"usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]},
            "choices": [{"message": {"tool_calls": [{"function": {"name": llm.TOOL, "arguments": json.dumps(args)}}]}}]}


class FakePost:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class LlmTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_diag(self, post, rendered="bundle"):
        return llm.diagnose(rendered, SCHEMA, validate, api_key=KEY, model="deepseek-v4.1-flash",
                            session_id="inc-1", cache_dir=self.tmp.name, post=post)

    def test_success_sends_go_headers_and_forced_tool(self):
        post = FakePost(reply({"confidence": 0.8}))
        result, meta = self.run_diag(post)
        self.assertEqual(result, {"confidence": 0.8})
        self.assertEqual((meta["attempts"], meta["tokens_in"], meta["tokens_out"], meta["cached"]), (1, 100, 20, False))
        url, headers, body, timeout = post.calls[0]
        self.assertEqual(url, "https://opencode.ai/inference/go/openai/v1/chat/completions")
        self.assertEqual(headers["x-opencode-session"], "inc-1")
        self.assertEqual(headers["User-Agent"], "oncall-agent/0.1")
        self.assertEqual(body["tool_choice"], {"type": "function", "function": {"name": "submit_diagnosis"}})
        self.assertEqual(body["tools"][0]["function"]["parameters"], SCHEMA)
        self.assertEqual(timeout, 30)
        self.assertNotIn(KEY, json.dumps(meta))

    def test_bad_answer_retries_once(self):
        result, meta = self.run_diag(FakePost(reply({"confidence": "high"}), reply({"confidence": 0.5})))
        self.assertEqual(result, {"confidence": 0.5})
        self.assertEqual((meta["attempts"], meta["errors"], meta["tokens_in"]), (2, ["ValueError"], 200))

    def test_two_failures_fall_back_to_cache(self):
        self.run_diag(FakePost(reply({"confidence": 0.9})))
        result, meta = self.run_diag(FakePost(TimeoutError(), {"choices": []}))
        self.assertEqual(result, {"confidence": 0.9})
        self.assertTrue(meta["cached"])
        self.assertEqual(meta["errors"], ["TimeoutError", "IndexError"])

    def test_two_failures_no_cache_gives_none(self):
        result, meta = self.run_diag(FakePost(TimeoutError(), TimeoutError()), rendered="other bundle")
        self.assertIsNone(result)
        self.assertEqual(meta["attempts"], 2)

    def test_missing_env_fails_loud_with_names_only(self):
        with mock.patch.dict(os.environ, {"OPENCODE_API_KEY": KEY}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                llm.config_from_env()
        self.assertIn("LLM_MODEL", str(ctx.exception))
        self.assertNotIn(KEY, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
