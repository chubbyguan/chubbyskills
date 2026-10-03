"""Offline regression tests for provider isolation and resumable paid jobs."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

SCRIPTS = Path(__file__).resolve().parents[1] / "podcast-transcribe" / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location("podcast_test_" + name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cloud = load_script("cloud_transcribe")

COMPLETION = {"choices": [{"finish_reason": "stop", "index": 0, "message": {"role": "assistant", "content": "恢复成功"}}],
              "id": "chatcmpl-1", "model": "qwen3-asr-flash", "object": "chat.completion"}


def completed(text):
    return {"choices": [{"finish_reason": "stop", "index": 0, "message": {"role": "assistant", "content": text}}]}


class PodcastProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.audio = self.root / "private source.mp3"
        self.audio.write_bytes(b"test audio content")
        self.state = self.root / "state"
        self.key_env = patch.dict(os.environ, {"DASHSCOPE_API_KEY": "secret-key"})
        self.key_env.start()

    def tearDown(self):
        self.key_env.stop()
        self.tmp.cleanup()

    def run_dashscope(self, **kwargs):
        return cloud.transcribe_cloud(self.audio, provider="dashscope", state_dir=self.state, **kwargs)

    def run_groq(self, **kwargs):
        return cloud.transcribe_cloud(self.audio, provider="groq", state_dir=self.state, **kwargs)

    def test_groq_auth_multipart_payload_and_synchronous_completed_path(self):
        calls = []

        def request_json(request, timeout):
            calls.append(request)
            return {"text": "你好，世界", "segments": [{"start": 0.0, "end": 1.5, "text": "你好，世界"}]}

        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "request_json", side_effect=request_json):
                result = self.run_groq(language="zh")
        self.assertEqual(result["text"], "你好，世界")
        self.assertEqual(result["segments"], [{"start": 0.0, "end": 1.5, "text": "你好，世界"}])
        self.assertFalse(result["cached"])
        self.assertEqual(len(calls), 1)
        request = calls[0]
        self.assertEqual(request.method, "POST")
        self.assertTrue(request.full_url.endswith("/openai/v1/audio/transcriptions"))
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-groq-key")
        content_type = request.get_header("Content-type")
        self.assertIn("multipart/form-data; boundary=", content_type)
        body = request.data
        self.assertIn(b'name="model"\r\n\r\nwhisper-large-v3-turbo', body)
        self.assertIn(b'name="response_format"\r\n\r\nverbose_json', body)
        self.assertIn(b'name="language"\r\n\r\nzh', body)
        self.assertIn(b'name="file"; filename="audio.mp3"', body)
        self.assertIn(b"test audio content", body)
        self.assertNotIn(str(self.audio).encode(), body)
        state_text = next(self.state.glob("*.json")).read_text()
        self.assertNotIn("secret-groq-key", state_text)
        self.assertNotIn(str(self.audio), state_text)
        # A completed result is replayed from cache without another billable POST.
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "request_json", side_effect=AssertionError("must use completed cache")):
                self.assertEqual(self.run_groq(language="zh")["text"], "你好，世界")

    def test_groq_language_omitted_when_empty_or_auto(self):
        calls = []
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "request_json", side_effect=lambda request, timeout: calls.append(request) or {"text": "hi"}):
                self.run_groq(language="")
                self.run_groq(language="auto")
        for request in calls:
            self.assertNotIn(b'name="language"', request.data)

    def test_groq_single_file_safety_net_still_rejects_oversized(self):
        with self.audio.open("wb") as stream:
            stream.truncate(cloud.GROQ_MAX_AUDIO_BYTES)
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            client = cloud.CloudProvider({"provider": "groq", "model": "whisper-large-v3-turbo", "language": "zh", "base_url": "https://api.groq.com/openai/v1"})
            with self.assertRaisesRegex(ValueError, "25MB"):
                client._prepare_groq(self.audio, 0)

    def _groq_chunks(self):
        return [(b"chunk-zero", cloud.hashlib.sha256(b"chunk-zero").hexdigest(), 10.0),
                (b"chunk-one", cloud.hashlib.sha256(b"chunk-one").hexdigest(), 5.0)]

    def _big_audio(self):
        with self.audio.open("wb") as stream:
            stream.truncate(cloud.GROQ_MAX_AUDIO_BYTES)

    def test_groq_long_audio_chunks_in_order_with_segment_offsets(self):
        self._big_audio()
        responses = [
            {"text": "第一段", "segments": [{"start": 0.0, "end": 2.0, "text": "第一段"}]},
            {"text": "第二段", "segments": [{"start": 0.5, "end": 1.5, "text": "第二段"}]},
        ]
        calls = []
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "_split_audio", side_effect=lambda path, deadline: self._groq_chunks()) as split:
                with patch.object(cloud, "request_json", side_effect=lambda request, timeout: (calls.append(request), responses.pop(0))[1]):
                    result = self.run_groq()
        self.assertEqual(split.call_count, 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["text"], "第一段\n第二段")
        # Second chunk segments shift by the first chunk's duration (10s).
        self.assertEqual(result["segments"], [
            {"start": 0.0, "end": 2.0, "text": "第一段"},
            {"start": 10.5, "end": 11.5, "text": "第二段"},
        ])
        state = json.loads(next(self.state.glob("*.json")).read_text())
        self.assertEqual(state["status"], "completed")
        self.assertEqual(sorted(state["chunks"]["completed"]), ["0", "1"])
        # Completed chunked results replay from cache with zero requests.
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "request_json", side_effect=AssertionError("must use completed cache")):
                self.assertEqual(self.run_groq()["text"], "第一段\n第二段")

    def test_groq_chunk_resume_never_resubmits_completed_chunks(self):
        self._big_audio()
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "_split_audio", side_effect=lambda path, deadline: self._groq_chunks()):
                calls = []

                def first_run(request, timeout):
                    calls.append(request)
                    if len(calls) == 2:
                        raise URLError("connection lost")
                    return {"text": "第一段", "segments": [{"start": 0.0, "end": 2.0, "text": "第一段"}]}

                with patch.object(cloud, "request_json", side_effect=first_run):
                    with self.assertRaisesRegex(RuntimeError, "chunk 2/2|resume"):
                        self.run_groq()
                state = json.loads(next(self.state.glob("*.json")).read_text())
                self.assertEqual(state["status"], "submitting")
                self.assertEqual(sorted(state["chunks"]["completed"]), ["0"])
                with patch.object(cloud, "request_json", return_value={"text": "第二段", "segments": []}) as request:
                    result = self.run_groq()
                self.assertEqual(request.call_count, 1)
                body = request.call_args.args[0].data
                self.assertIn(b"chunk-one", body)
                self.assertNotIn(b"chunk-zero", body)
        self.assertEqual(result["text"], "第一段\n第二段")

    def test_groq_chunk_plan_mismatch_blocks_resume(self):
        self._big_audio()
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "_split_audio", side_effect=lambda path, deadline: self._groq_chunks()):
                with patch.object(cloud, "request_json", side_effect=URLError("lost")):
                    with self.assertRaises(RuntimeError):
                        self.run_groq()
                changed = [(b"different", cloud.hashlib.sha256(b"different").hexdigest(), 10.0)]
                with patch.object(cloud, "_split_audio", side_effect=lambda path, deadline: changed):
                    with patch.object(cloud, "request_json") as request:
                        with self.assertRaisesRegex(RuntimeError, "chunk plan|resubmit"):
                            self.run_groq()
                        request.assert_not_called()

    def test_groq_chunk_429_waits_retry_after_then_succeeds(self):
        self._big_audio()
        error = HTTPError("https://api.groq.com/openai/v1/audio/transcriptions", 429, "rate limited", {"Retry-After": "1"}, None)
        responses = [error, {"text": "第一段", "segments": []}, {"text": "第二段", "segments": []}]
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "_split_audio", side_effect=lambda path, deadline: self._groq_chunks()):
                with patch.object(cloud, "request_json") as request, patch.object(cloud.time, "sleep") as sleep:
                    def respond(req, timeout):
                        item = responses.pop(0)
                        if isinstance(item, Exception):
                            raise item
                        return item
                    request.side_effect = respond
                    result = self.run_groq()
        self.assertEqual(result["text"], "第一段\n第二段")
        self.assertEqual(request.call_count, 3)
        sleep.assert_called_once_with(1.0)

    def test_groq_chunking_requires_ffmpeg(self):
        self._big_audio()
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud.shutil, "which", return_value=None), patch.object(cloud, "request_json") as request:
                with self.assertRaisesRegex(RuntimeError, "ffmpeg"):
                    self.run_groq()
                request.assert_not_called()

    def test_groq_missing_or_invalid_key_fails_before_any_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "GROQ_API_KEY"):
                self.run_groq()
            request.assert_not_called()
        with patch.dict(os.environ, {"GROQ_API_KEY": "bad\nkey"}), patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "GROQ_API_KEY"):
                self.run_groq()
            request.assert_not_called()

    def test_groq_empty_text_fails_with_saved_ambiguous_state(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(cloud, "request_json", return_value={"text": "  ", "segments": []}):
                with self.assertRaises(RuntimeError):
                    self.run_groq()
        state = json.loads(next(self.state.glob("*.json")).read_text())
        self.assertEqual(state["status"], "ambiguous")

    def test_groq_export_keeps_timestamp_segments(self):
        transcribe = load_script("transcribe")
        original_sibling = transcribe._sibling
        output = self.root / "groq.md"
        response = {"text": "第一句。第二句。", "segments": [{"start": 0, "end": 1, "text": "第一句。"}, {"start": 1, "end": 2, "text": "第二句。"}]}
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret-groq-key"}):
            with patch.object(transcribe, "_sibling", side_effect=lambda name: cloud if name == "cloud_transcribe" else original_sibling(name)), patch.object(cloud, "request_json", return_value=response):
                transcribe.transcribe_audio(str(self.audio), str(output), "Groq", provider="groq", state_dir=self.state)
        text = output.read_text()
        self.assertIn("第一句。第二句。", text)
        self.assertIn("时间戳参考", text)
        self.assertIn("transcription_provider: groq", text)
        self.assertIn('transcription_model: "whisper-large-v3-turbo"', text)

    def test_dashscope_auth_payload_and_synchronous_completed_path(self):
        calls = []

        def request_json(request, timeout):
            calls.append(request)
            return completed("你好，世界")

        with patch.object(cloud, "request_json", side_effect=request_json):
            result = self.run_dashscope(language="zh")
        self.assertEqual(result["text"], "你好，世界")
        self.assertFalse(result["cached"])
        self.assertEqual(len(calls), 1)
        request = calls[0]
        self.assertEqual(request.method, "POST")
        self.assertTrue(request.full_url.endswith("/compatible-mode/v1/chat/completions"))
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-key")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "qwen3-asr-flash")
        audio = payload["messages"][0]["content"][0]["input_audio"]
        self.assertEqual(payload["messages"][0]["content"][0]["type"], "input_audio")
        self.assertEqual(audio["format"], "mp3")
        self.assertTrue(audio["data"].startswith("data:audio/mpeg;base64,"))
        self.assertEqual(payload["asr_options"], {"enable_itn": True, "language": "zh"})
        state_text = next(self.state.glob("*.json")).read_text()
        self.assertNotIn("secret-key", state_text)
        self.assertNotIn(str(self.audio), state_text)
        # A completed result is replayed from cache without another billable POST.
        with patch.object(cloud, "request_json", side_effect=AssertionError("must use completed cache")):
            self.assertEqual(self.run_dashscope(language="zh")["text"], "你好，世界")

    def test_dashscope_rejects_oversized_audio_before_any_request(self):
        with self.audio.open("wb") as stream:
            stream.truncate(cloud.DASHSCOPE_MAX_AUDIO_BYTES + 1)
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "SenseVoice"):
                self.run_dashscope()
            request.assert_not_called()

    def test_missing_or_invalid_key_fails_before_any_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "DASHSCOPE_API_KEY"):
                self.run_dashscope()
            request.assert_not_called()
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "bad\nkey"}), patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "DASHSCOPE_API_KEY"):
                self.run_dashscope()
            request.assert_not_called()

    def test_invalid_completion_shapes_fail_with_saved_ambiguous_state(self):
        for response in [{"choices": []}, {"choices": [{"message": {"content": ""}}]}, {"id": "x"}]:
            with self.subTest(response=response):
                with patch.object(cloud, "request_json", return_value=response):
                    with self.assertRaises(RuntimeError):
                        self.run_dashscope()
                state = json.loads(next(self.state.glob("*.json")).read_text())
                self.assertEqual(state["status"], "ambiguous")
                state_file = next(self.state.glob("*.json"))
                state_file.unlink()

    def test_lost_submission_response_requires_explicit_resubmit(self):
        with patch.object(cloud, "request_json", side_effect=URLError("secret-key")) as request:
            with self.assertRaisesRegex(RuntimeError, "ambiguous|不确定"):
                self.run_dashscope()
            self.assertEqual(request.call_count, 1)
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "resubmit"):
                self.run_dashscope()
            request.assert_not_called()
        with patch.object(cloud, "request_json", return_value=completed("new")) as request:
            self.assertEqual(self.run_dashscope(resubmit=True)["text"], "new")
            self.assertEqual(request.call_count, 1)

    def test_provider_model_language_and_content_separate_paid_cache(self):
        with patch.object(cloud, "request_json", return_value=completed("text")) as request:
            self.run_dashscope()
            self.run_dashscope(language="en")
            self.run_dashscope(model="qwen3-asr-flash-2025")
            self.audio.write_bytes(b"different audio")
            self.run_dashscope()
            self.assertEqual(request.call_count, 4)
        self.assertEqual(len(list(self.state.glob("*.json"))), 4)

    def test_invalid_settings_fail_without_network(self):
        bad_bases = ["http://api.example/v1", "https://key@api.example/v1", "https://api.example/v1?key=secret", "https://api.example/#fragment", "https://api.example/\nsecret"]
        with patch.object(cloud, "request_json") as request:
            for base in bad_bases:
                with self.subTest(base=base), self.assertRaises(ValueError):
                    self.run_dashscope(base_url=base)
            for value in [float("nan"), float("inf"), -1, 0]:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    self.run_dashscope(cloud_timeout=value)
            with self.assertRaises(ValueError):
                self.run_dashscope(poll_interval=float("nan"))
            request.assert_not_called()

    def test_redirects_never_forward_authenticated_requests(self):
        handler = cloud.NoRedirect()
        from urllib.request import Request
        for location in ["https://attacker.invalid/capture", "http://dashscope.aliyuncs.com/capture", "https://dashscope.aliyuncs.com/other"]:
            request = Request("https://dashscope.aliyuncs.com/compatible-mode/v1", headers={"Authorization": "Bearer secret-key"})
            self.assertIsNone(handler.redirect_request(request, None, 302, "Found", {}, location))

    def test_dashscope_has_no_polling_endpoint(self):
        client = cloud.CloudProvider({"provider": "dashscope", "model": "qwen3-asr-flash", "language": "zh", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"})
        with self.assertRaisesRegex(RuntimeError, "synchronous"):
            client.poll("task-id", 0)

    def test_corrupt_state_does_not_resubmit(self):
        with patch.object(cloud, "request_json", return_value=completed("done")):
            self.run_dashscope()
        next(self.state.glob("*.json")).write_text("broken JSON")
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "state|状态"):
                self.run_dashscope()
            request.assert_not_called()

    def test_output_failure_reuses_paid_result_and_preserves_existing_files(self):
        transcribe = load_script("transcribe")
        original_sibling = transcribe._sibling
        output = self.root / "output.md"
        responses = completed("cached transcript")
        with patch.object(transcribe, "_sibling", side_effect=lambda name: cloud if name == "cloud_transcribe" else original_sibling(name)):
            with patch.object(cloud, "request_json", return_value=responses) as request:
                output.write_text("user edited original")
                with self.assertRaises(FileExistsError):
                    transcribe.transcribe_audio(str(self.audio), str(output), "Title: special", provider="dashscope", state_dir=self.state)
                self.assertEqual(output.read_text(), "user edited original")
                request.assert_not_called()
                second = self.root / "new.md"
                with patch.object(transcribe, "open", side_effect=OSError("disk full"), create=True), self.assertRaises(OSError):
                    transcribe.transcribe_audio(str(self.audio), str(second), "Title: special", provider="dashscope", state_dir=self.state)
                self.assertEqual(request.call_count, 1)
                transcribe.transcribe_audio(str(self.audio), str(second), "Title: special", provider="dashscope", state_dir=self.state)
                self.assertEqual(request.call_count, 1)
                self.assertIn("cached transcript", second.read_text())
                self.assertIn('title: "Title: special"', second.read_text())

    def test_batch_explicit_local_overrides_environment_and_uses_real_output(self):
        batch = load_script("batch_transcribe")
        output = self.root / "actual-local-output.md"
        output.write_text("new transcript")
        old = self.root / "EP001-test.md"
        old.write_text("old cloud transcript" * 100)
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "dashscope"}):
            with patch.object(batch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, str(output) + "\n", "")) as run:
                actual = batch.transcribe_episode(str(self.audio), str(self.root), {"num": 1, "title": "test"}, provider="local")
        self.assertEqual(actual, str(output))
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--provider") + 1], "local")
        self.assertEqual(command[command.index("--model") + 1], "SenseVoiceSmall")
        self.assertNotEqual(actual, str(old))

    def test_batch_forwards_cloud_identity_and_failures_return_none(self):
        batch = load_script("batch_transcribe")
        result = subprocess.CompletedProcess([], 1, "", "secret-key")
        with patch.object(batch.subprocess, "run", return_value=result) as run:
            self.assertIsNone(batch.transcribe_episode(str(self.audio), str(self.root), {}, provider="dashscope", model="qwen3-asr-flash", base_url="https://endpoint.example/v1", state_dir=self.state, language="en", resubmit=True))
        command = run.call_args.args[0]
        for flag, value in [("--provider", "dashscope"), ("--model", "qwen3-asr-flash"), ("--base-url", "https://endpoint.example/v1"), ("--state-dir", str(self.state)), ("--language", "en")]:
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("--resubmit", command)

    def _patch_local_funasr(self, text):
        from chubby_common import funasr
        return patch.object(funasr, "transcribe", return_value=(text, 0.5))

    def test_explicit_local_cli_works_without_any_cloud_key_and_keeps_previous_output(self):
        transcribe = load_script("transcribe")
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "dashscope"}), self._patch_local_funasr("local transcript"):
            self.assertEqual(transcribe.main([str(self.audio), str(self.root), "--provider", "local"]), 0)
            outputs = list(self.root.glob("*.md"))
            self.assertEqual(len(outputs), 1)
            outputs[0].write_text("user changes")
            self.assertEqual(transcribe.main([str(self.audio), str(self.root), "--provider", "local"]), 0)
        self.assertEqual(len(list(self.root.glob("*.md"))), 2)
        self.assertEqual(outputs[0].read_text(), "user changes")

    def test_title_override_uses_subscription_episode_title(self):
        transcribe = load_script("transcribe")
        with self._patch_local_funasr("本地转写"):
            self.assertEqual(transcribe.main([str(self.audio), str(self.root), "--provider", "local", "--title", "EP.04 美元人民币汇率同涨真相"]), 0)
        output = next(self.root.glob("*.md"))
        content = output.read_text()
        self.assertIn('title: "EP.04 美元人民币汇率同涨真相"', content)
        self.assertIn('transcriber: "sensevoice-small"', content)
        self.assertIn("段数：1", content)

    def test_local_language_default_and_auto_passthrough(self):
        transcribe = load_script("transcribe")
        from chubby_common import funasr
        with patch.object(funasr, "transcribe", return_value=("text", 0.1)) as call:
            self.assertEqual(transcribe.main([str(self.audio), str(self.root), "--provider", "local"]), 0)
            self.assertEqual(call.call_args.kwargs["language"], "zh")
            self.assertEqual(transcribe.main([str(self.audio), str(self.root), "--provider", "local", "--language", ""]), 0)
            self.assertEqual(call.call_args.kwargs["language"], "auto")

    def test_local_qwen_model_dispatches_to_qwen_backend(self):
        transcribe = load_script("transcribe")
        qwen = load_script("local_qwen_asr")
        original_sibling = transcribe._sibling
        from chubby_common import funasr
        with patch.object(transcribe, "_sibling", side_effect=lambda name: qwen if name == "local_qwen_asr" else original_sibling(name)):
            with patch.object(qwen, "transcribe", return_value=("岩茶与朱伟", 240.0)) as call, patch.object(funasr, "transcribe", side_effect=AssertionError("must not use funasr")):
                self.assertEqual(transcribe.main([str(self.audio), str(self.root), "--provider", "local", "--model", "qwen3-asr-0.6b"]), 0)
        self.assertEqual(call.call_args.kwargs["language"], "zh")
        output = next(self.root.glob("*.md")).read_text()
        self.assertIn("岩茶与朱伟", output)
        self.assertIn('transcriber: "qwen3-asr-0.6b"', output)
        self.assertIn('transcription_model: "qwen3-asr-0.6b"', output)

    def test_local_model_whitelist_rejects_unknown_models_without_loading(self):
        config_module = load_script("provider_config")
        with self.assertRaisesRegex(ValueError, "SenseVoiceSmall"):
            config_module.resolve_provider_config(provider="local", model="tiny", state_dir=self.state)
        result = subprocess.run([sys.executable, str(SCRIPTS / "transcribe.py"), str(self.audio), str(self.root), "--provider", "local", "--model", "whisper-large"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("SenseVoiceSmall", result.stderr)
        self.assertFalse(list(self.root.glob("*.md")))

    def test_local_qwen_missing_dependency_prints_install_hint(self):
        qwen = load_script("local_qwen_asr")
        import importlib.util
        import io
        from contextlib import redirect_stderr
        stderr = io.StringIO()
        with patch.object(importlib.util, "find_spec", return_value=None), redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                qwen.transcribe(str(self.audio))
        self.assertIn("pip install qwen-asr transformers torch", stderr.getvalue())

    def test_ambiguous_crash_marker_and_active_lock_block_duplicate_post(self):
        import fcntl
        with patch.object(cloud, "request_json", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_dashscope()
        state = json.loads(next(self.state.glob("*.json")).read_text())
        self.assertEqual(state["status"], "submitting")
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "resubmit"):
                self.run_dashscope()
            request.assert_not_called()
            with next(self.state.glob("*.lock")).open("r+") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, "already running"):
                    self.run_dashscope(resubmit=True)
                request.assert_not_called()

    def test_audio_changed_during_preparation_never_submits_paid_job(self):
        original_prepare = cloud.CloudProvider.prepare
        def changed(client, audio_path, deadline):
            payload = original_prepare(client, audio_path, deadline)
            self.audio.write_bytes(b"changed while preparing")
            return payload
        with patch.object(cloud.CloudProvider, "prepare", changed), patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "changed"):
                self.run_dashscope()
            request.assert_not_called()

    def test_config_defaults_are_portable_and_environment_free_when_explicit(self):
        config_module = load_script("provider_config")
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "dashscope", "DASHSCOPE_BASE_URL": "https://other.example/v1"}):
            config = config_module.resolve_provider_config(provider="local", state_dir=self.state)
            self.assertEqual(config["provider"], "local")
            self.assertEqual(config["base_url"], "")
            self.assertEqual(config["model"], "SenseVoiceSmall")
            explicit = config_module.resolve_provider_config(provider="dashscope", base_url="https://stable.example/v1", state_dir=self.state)
            self.assertEqual(explicit["base_url"], "https://stable.example/v1")
        self.assertNotIn("key", json.dumps(config).lower())

    def test_cloud_export_writes_full_text_and_frontmatter(self):
        transcribe = load_script("transcribe")
        original_sibling = transcribe._sibling
        output = self.root / "full-text.md"
        with patch.object(transcribe, "_sibling", side_effect=lambda name: cloud if name == "cloud_transcribe" else original_sibling(name)), patch.object(cloud, "request_json", return_value=completed("第一句。第二句。")):
            transcribe.transcribe_audio(str(self.audio), str(output), "Full text", provider="dashscope", state_dir=self.state)
        text = output.read_text()
        self.assertIn("第一句。第二句。", text)
        self.assertIn("transcription_provider: dashscope", text)
        self.assertIn('transcription_model: "qwen3-asr-flash"', text)

    def test_actual_cli_rejects_resubmit_abbreviations(self):
        commands = [("transcribe.py", [str(self.audio), str(self.root)]), ("batch_transcribe.py", ["--rss-url", "https://public.example/feed"])]
        for script, arguments in commands:
            result = subprocess.run([sys.executable, str(SCRIPTS / script), *arguments, "--resub"], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("unrecognized arguments: --resub", result.stderr)

    def test_download_urls_block_local_files_credentials_and_private_dns(self):
        download = load_script("safe_download")
        urls = [self.audio.as_uri(), "ftp://public.example/a.mp3", "https://user:pass@public.example/audio.mp3", "http://127.0.0.1/a.mp3", "http://[::1]/audio.mp3", "http://169.254.169.254/audio.mp3", "https://public.example/\\private", "https://public.example/a\n.mp3", "https://private.example/audio.mp3"]
        with patch.object(download.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 443))]), patch.object(download.subprocess, "run") as run:
            for url in urls:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    download.download(url, self.root / "forbidden.mp3")
            run.assert_not_called()
        self.assertEqual(self.audio.read_bytes(), b"test audio content")

    def test_public_download_pins_dns_and_does_not_follow_redirect(self):
        download = load_script("safe_download")
        calls = []
        def redirect(command, **kwargs):
            calls.append(command)
            Path(command[command.index("--output") + 1]).write_bytes(b"redirect to file:///private/secret")
            return subprocess.CompletedProcess(command, 0, "302", "")
        with patch.object(download.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), patch.object(download.subprocess, "run", side_effect=redirect):
            with self.assertRaisesRegex(RuntimeError, "redirect"):
                download.download("https://public.example/audio.mp3", self.root / "redirected.mp3")
        self.assertEqual(len(calls), 1)
        command = calls[0]
        self.assertEqual(command[:2], ["curl", "--disable"])
        self.assertEqual(command[-2:], ["--", "https://public.example/audio.mp3"])
        self.assertEqual(command[command.index("--resolve") + 1], "public.example:443:93.184.216.34")
        self.assertEqual(command[command.index("--proto") + 1], "=http,https")
        self.assertEqual(command[command.index("--proto-redir") + 1], "=http,https")
        self.assertEqual(command[command.index("--noproxy") + 1], "*")
        self.assertNotIn("-L", command)
        self.assertNotIn("--location", command)
        self.assertFalse((self.root / "redirected.mp3").exists())

    def test_untrusted_html_audio_cannot_read_private_file_or_upload(self):
        transcribe = load_script("transcribe")
        download = load_script("safe_download")
        original_sibling = transcribe._sibling
        html = f'<title>Malicious</title><meta property="og:audio" content="{self.audio.as_uri()}">'
        with patch.object(transcribe, "_sibling", side_effect=lambda name: download if name == "safe_download" else original_sibling(name)), patch.object(download, "fetch_text", return_value=html), patch.object(download.subprocess, "run") as curl, patch.object(cloud, "request_json") as upload:
            self.assertEqual(transcribe.main(["https://public.example/episode/1", str(self.root), "--provider", "dashscope", "--state-dir", str(self.state)]), 1)
            curl.assert_not_called()
            upload.assert_not_called()
        self.assertFalse(self.state.exists())
        self.assertEqual(self.audio.read_bytes(), b"test audio content")

    def test_rss_enclosure_cannot_read_private_file(self):
        batch = load_script("batch_transcribe")
        download = load_script("safe_download")
        original_sibling = batch._sibling
        rss = f'<rss><channel><item><title>Bad episode</title><enclosure url="{self.audio.as_uri()}"/></item></channel></rss>'
        with patch.object(batch, "_sibling", side_effect=lambda name: download if name == "safe_download" else original_sibling(name)), patch.object(download, "fetch_text", return_value=rss), patch.object(download.subprocess, "run") as curl:
            episodes = batch.parse_rss("https://public.example/feed")
            old = self.root / "EP001-Bad-episode.m4a"
            old.write_bytes(b"cached audio" * 10000)
            self.assertIsNone(batch.download_episode(episodes[0], str(self.root)))
            curl.assert_not_called()
        self.assertEqual(self.audio.read_bytes(), b"test audio content")

    def test_rejected_rss_source_never_reaches_transcription_even_with_cache(self):
        batch = load_script("batch_transcribe")
        download = load_script("safe_download")
        original_sibling = batch._sibling
        rss = f'<rss><channel><item><title>Bad episode</title><enclosure url="{self.audio.as_uri()}"/></item></channel></rss>'
        audio_dir = self.root / "audio"
        audio_dir.mkdir()
        (audio_dir / "EP001-Bad-episode.m4a").write_bytes(b"cached audio" * 10000)
        with patch.object(batch, "_sibling", side_effect=lambda name: download if name == "safe_download" else original_sibling(name)), patch.object(download, "fetch_text", return_value=rss), patch.object(batch, "transcribe_episode") as transcribe:
            for extra in [[], ["--transcribe-only"]]:
                self.assertEqual(batch.main(["--rss-url", "https://public.example/feed", "--output", str(self.root), *extra]), 1)
            transcribe.assert_not_called()

    def test_scripts_import_in_isolated_mode(self):
        for path in SCRIPTS.glob("*.py"):
            result = subprocess.run([sys.executable, "-I", "-c", "import runpy,sys; runpy.run_path(sys.argv[1], run_name='portable_probe')", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class SafeDownloadAddressTest(unittest.TestCase):
    def test_fake_ip_dns_answers_are_allowed_but_private_addresses_rejected(self):
        safe_download = load_script("safe_download")
        fake = [(2, 1, 6, "", ("198.18.0.3", 443))]
        private = [(2, 1, 6, "", ("10.0.0.8", 443))]
        with patch.object(safe_download.socket, "getaddrinfo", return_value=fake):
            _, host, _, address = safe_download.public_url("https://cdn.example.com/a.m4a")
            self.assertEqual((host, address), ("cdn.example.com", "198.18.0.3"))
        with patch.object(safe_download.socket, "getaddrinfo", return_value=private):
            with self.assertRaises(ValueError):
                safe_download.public_url("https://cdn.example.com/a.m4a")

    def test_redirect_chain_is_chased_with_per_hop_validation(self):
        safe_download = load_script("safe_download")
        public = [(2, 1, 6, "", ("93.184.216.34", 443))]

        def probe(command, **kwargs):
            if "track" in command[-1]:
                return subprocess.CompletedProcess(command, 0, "302\thttps://cdn.example.com/final.m4a", "")
            return subprocess.CompletedProcess(command, 0, "200\t", "")

        with patch.object(
            safe_download.socket, "getaddrinfo", return_value=public
        ), patch.object(safe_download.subprocess, "run", side_effect=probe):
            final = safe_download.resolve_redirects(
                "https://dts-api.example.com/track/abc/media.m4a"
            )
        self.assertEqual(final, "https://cdn.example.com/final.m4a")

    def test_redirect_to_private_address_is_rejected(self):
        safe_download = load_script("safe_download")

        def probe(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "302\thttps://evil.example/x.m4a", "")

        def resolve_private(host, port, type=None):
            if "evil" in host:
                return [(2, 1, 6, "", ("127.0.0.1", 443))]
            return [(2, 1, 6, "", ("93.184.216.34", 443))]

        with patch.object(
            safe_download.socket, "getaddrinfo", side_effect=resolve_private
        ), patch.object(safe_download.subprocess, "run", side_effect=probe):
            with self.assertRaises(ValueError):
                safe_download.resolve_redirects("https://dts-api.example.com/track/abc")


if __name__ == "__main__":
    unittest.main()
