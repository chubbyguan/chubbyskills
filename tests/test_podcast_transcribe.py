import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "podcast-transcribe", "scripts", "transcribe.py")
SPEC = importlib.util.spec_from_file_location("podcast_transcribe", SCRIPT)
TRANSCRIBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSCRIBE)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeMuapiHTTP:
    def __init__(self):
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if request.full_url.endswith("/upload_file"):
            return FakeResponse({"url": "https://media.example/audio.m4a"})
        if request.full_url.endswith("/openai-whisper"):
            return FakeResponse({"id": "request/1"})
        if request.full_url.endswith("/predictions/request%2F1/result"):
            return FakeResponse(
                {
                    "status": "succeeded",
                    "output": {
                        "text": "你好，世界。",
                        "segments": [
                            {"start": 0, "end": 1.5, "text": "你好，世界。"}
                        ],
                    },
                }
            )
        raise AssertionError(f"Unexpected URL: {request.full_url}")


class MuapiTranscribeTest(unittest.TestCase):
    def test_transcribes_and_formats_verbose_result(self):
        fake_http = FakeMuapiHTTP()
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "episode.m4a")
            output_path = os.path.join(tmpdir, "episode.md")
            with open(audio_path, "wb") as audio_file:
                audio_file.write(b"audio")

            with patch.dict(os.environ, {"MUAPI_API_KEY": "test-key"}, clear=False), \
                    patch.object(TRANSCRIBE, "urlopen", fake_http), \
                    patch.object(TRANSCRIBE.time, "sleep"):
                elapsed, segment_count = TRANSCRIBE.transcribe_audio_muapi(
                    audio_path, output_path, "Episode", source="local.m4a", language="zh"
                )

            self.assertGreaterEqual(elapsed, 0)
            self.assertEqual(segment_count, 1)
            with open(output_path, encoding="utf-8") as output_file:
                markdown = output_file.read()
            self.assertIn("transcriber: muapi-openai-whisper", markdown)
            self.assertIn("[   0.0s ->    1.5s] 你好，世界。", markdown)

            api_calls = [request for request, _timeout in fake_http.calls]
            self.assertEqual(len(api_calls), 3)
            self.assertTrue(all(request.get_header("X-api-key") == "test-key" for request in api_calls))
            self.assertIn("audio_url", json.loads(api_calls[1].data.decode("utf-8")))

    def test_missing_key_is_reported_before_network_call(self):
        with patch.dict(os.environ, {"MUAPI_API_KEY": "", "MU_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "MUAPI_API_KEY"):
                TRANSCRIBE.transcribe_audio_muapi("missing.m4a", "out.md", "Episode")


if __name__ == "__main__":
    unittest.main()
