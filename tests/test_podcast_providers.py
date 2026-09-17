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


class PodcastProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.audio = self.root / "private source.mp3"
        self.audio.write_bytes(b"test audio content")
        self.state = self.root / "state"
        self.key_env = patch.dict(os.environ, {"ATLAS_API_KEY": "secret-key", "MUAPI_API_KEY": "secret-mu-key"})
        self.key_env.start()

    def tearDown(self):
        self.key_env.stop()
        self.tmp.cleanup()

    def run_atlas(self, **kwargs):
        return cloud.transcribe_cloud(self.audio, provider="atlas", state_dir=self.state, **kwargs)

    def test_task_id_persisted_before_poll_and_retry_never_posts(self):
        def first_request(request, timeout):
            if request.method == "POST":
                return {"data": {"id": "task/123", "status": "processing"}}
            state = json.loads(next(self.state.glob("*.json")).read_text())
            self.assertEqual(state["task_id"], "task/123")
            self.assertEqual(state["status"], "pending")
            raise TimeoutError("do not leak secret-key https://signed.test/?token=secret")

        with patch.object(cloud, "request_json", side_effect=first_request):
            with self.assertRaisesRegex(RuntimeError, "saved|保存") as error:
                self.run_atlas(cloud_timeout=0.05, poll_interval=0.01)
        self.assertNotIn("secret-key", str(error.exception))
        calls = []

        def resumed(request, timeout):
            calls.append(request)
            return {"data": {"id": "task/123", "status": "completed", "stt_result": {"text": "恢复成功"}}}

        with patch.object(cloud, "request_json", side_effect=resumed):
            result = self.run_atlas()
        self.assertEqual(result["text"], "恢复成功")
        self.assertEqual([request.method for request in calls], ["GET"])
        self.assertTrue(calls[0].full_url.endswith("task%2F123"))
        state_text = next(self.state.glob("*.json")).read_text()
        self.assertNotIn("secret", state_text)
        self.assertNotIn(str(self.audio), state_text)
        with patch.object(cloud, "request_json", side_effect=AssertionError("must use completed cache")):
            self.assertEqual(self.run_atlas()["text"], "恢复成功")

    def test_returned_task_id_survives_malformed_or_error_submission_envelope(self):
        with patch.object(cloud, "request_json", return_value={"id": "known-task", "code": 400, "data": None}):
            with self.assertRaises(RuntimeError):
                self.run_atlas()
        state = json.loads(next(self.state.glob("*.json")).read_text())
        self.assertEqual(state["task_id"], "known-task")
        self.assertEqual(state["status"], "pending")
        with patch.object(cloud, "request_json", return_value={"status": "completed", "text": "recovered"}) as request:
            self.assertEqual(self.run_atlas()["text"], "recovered")
            self.assertEqual(request.call_args.args[0].method, "GET")

    def test_lost_submission_response_requires_explicit_resubmit(self):
        with patch.object(cloud, "request_json", side_effect=URLError("secret-key")) as request:
            with self.assertRaisesRegex(RuntimeError, "ambiguous|不确定"):
                self.run_atlas()
            self.assertEqual(request.call_count, 1)
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "resubmit"):
                self.run_atlas()
            request.assert_not_called()
        with patch.object(cloud, "request_json", return_value={"data": {"id": "new-id", "status": "completed", "stt_result": {"text": "new"}}}) as request:
            self.assertEqual(self.run_atlas(resubmit=True)["text"], "new")
            self.assertEqual(request.call_count, 1)

    def test_provider_model_language_and_content_separate_paid_cache(self):
        with patch.object(cloud, "request_json", return_value={"data": {"id": "id", "status": "completed", "stt_result": {"text": "text"}}}) as request:
            self.run_atlas()
            self.run_atlas(language="en")
            self.run_atlas(model="another/model")
            self.audio.write_bytes(b"different audio")
            self.run_atlas()
            self.assertEqual(request.call_count, 4)
        self.assertEqual(len(list(self.state.glob("*.json"))), 4)

    def test_invalid_settings_fail_without_network(self):
        bad_bases = ["http://api.example/v1", "https://key@api.example/v1", "https://api.example/v1?key=secret", "https://api.example/#fragment", "https://api.example/\nsecret"]
        with patch.object(cloud, "request_json") as request:
            for base in bad_bases:
                with self.subTest(base=base), self.assertRaises(ValueError):
                    self.run_atlas(base_url=base)
            for value in [float("nan"), float("inf"), -1, 0]:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    self.run_atlas(cloud_timeout=value)
            with self.assertRaises(ValueError):
                self.run_atlas(poll_interval=float("nan"))
            request.assert_not_called()

    def test_redirects_never_forward_authenticated_requests(self):
        handler = cloud.NoRedirect()
        from urllib.request import Request
        for location in ["https://attacker.invalid/capture", "http://api.atlascloud.ai/capture", "https://api.atlascloud.ai/other"]:
            request = Request("https://api.atlascloud.ai/api/v1", headers={"Authorization": "Bearer secret-key"})
            self.assertIsNone(handler.redirect_request(request, None, 302, "Found", {}, location))

    def test_muapi_upload_submit_poll_shared_lifecycle(self):
        calls = []
        responses = [{"url": "https://storage.example/audio?token=private"}, {"request_id": "mu/123"}, {"status": "completed", "output": {"text": "你好", "segments": [{"start": 1.0, "end": 2.0, "text": "你好"}]}}]

        def request_json(request, timeout):
            calls.append(request)
            return responses.pop(0)

        with patch.object(cloud, "request_json", side_effect=request_json):
            result = cloud.transcribe_cloud(self.audio, provider="muapi", state_dir=self.state)
        self.assertEqual([request.method for request in calls], ["POST", "POST", "GET"])
        self.assertTrue(calls[1].full_url.endswith("/openai-whisper"))
        self.assertIn("mu%2F123", calls[2].full_url)
        self.assertIn("你好", result["text"])
        saved = next(self.state.glob("*.json")).read_text()
        self.assertNotIn("token=private", saved)
        self.assertNotIn("secret-mu-key", saved)

    def test_muapi_outer_status_and_nested_transcript_are_preserved(self):
        responses = [{"url": "https://storage.example/audio"}, {"request_id": "mu-id"}, {"status": "completed", "data": {"output": "nested transcript"}}]
        with patch.object(cloud, "request_json", side_effect=responses):
            result = cloud.transcribe_cloud(self.audio, provider="muapi", state_dir=self.state)
        self.assertEqual(result["text"], "nested transcript")

    def test_muapi_size_and_upload_url_validation(self):
        with self.audio.open("wb") as stream:
            stream.truncate(25 * 1024 * 1024)
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "25"):
                cloud.transcribe_cloud(self.audio, provider="muapi", state_dir=self.state)
            request.assert_not_called()
        self.audio.write_bytes(b"small")
        with patch.object(cloud, "request_json", return_value={"url": "https://key@storage.example/audio"}) as request:
            with self.assertRaisesRegex(RuntimeError, "upload|上传"):
                cloud.transcribe_cloud(self.audio, provider="muapi", state_dir=self.state)
            self.assertEqual(request.call_count, 1)

    def test_failed_job_and_corrupt_state_do_not_resubmit(self):
        responses = [{"data": {"id": "id", "status": "processing"}}, {"data": {"status": "failed", "error": "secret-key"}}]
        with patch.object(cloud, "request_json", side_effect=responses):
            with self.assertRaises(RuntimeError) as error:
                self.run_atlas()
        self.assertNotIn("secret-key", str(error.exception))
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "resubmit"):
                self.run_atlas()
            request.assert_not_called()
        next(self.state.glob("*.json")).write_text("broken JSON")
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "state|状态"):
                self.run_atlas()
            request.assert_not_called()

    def test_poll_transient_errors_have_bounded_timeout_and_preserve_job(self):
        calls = []

        def request_json(request, timeout):
            calls.append(timeout)
            if request.method == "POST":
                return {"data": {"id": "id", "status": "processing"}}
            raise HTTPError(request.full_url, 503, "bad", {}, None)

        with patch.object(cloud, "request_json", side_effect=request_json):
            with self.assertRaises(RuntimeError):
                self.run_atlas(cloud_timeout=0.04, poll_interval=0.01)
        self.assertTrue(all(0 < timeout <= 0.04 for timeout in calls))
        self.assertEqual(json.loads(next(self.state.glob("*.json")).read_text())["status"], "pending")

    def test_output_failure_reuses_paid_result_and_preserves_existing_files(self):
        transcribe = load_script("transcribe")
        original_sibling = transcribe._sibling
        output = self.root / "output.md"
        responses = {"data": {"id": "id", "status": "completed", "stt_result": {"text": "cached transcript"}}}
        with patch.object(transcribe, "_sibling", side_effect=lambda name: cloud if name == "cloud_transcribe" else original_sibling(name)):
            with patch.object(cloud, "request_json", return_value=responses) as request:
                output.write_text("user edited original")
                with self.assertRaises(FileExistsError):
                    transcribe.transcribe_audio(str(self.audio), str(output), "Title: special", provider="atlas", state_dir=self.state)
                self.assertEqual(output.read_text(), "user edited original")
                request.assert_not_called()
                second = self.root / "new.md"
                with patch.object(transcribe, "open", side_effect=OSError("disk full"), create=True), self.assertRaises(OSError):
                    transcribe.transcribe_audio(str(self.audio), str(second), "Title: special", provider="atlas", state_dir=self.state)
                self.assertEqual(request.call_count, 1)
                transcribe.transcribe_audio(str(self.audio), str(second), "Title: special", provider="atlas", state_dir=self.state)
                self.assertEqual(request.call_count, 1)
                self.assertIn("cached transcript", second.read_text())
                self.assertIn('title: "Title: special"', second.read_text())

    def test_batch_explicit_local_overrides_environment_and_uses_real_output(self):
        batch = load_script("batch_transcribe")
        output = self.root / "actual-local-output.md"
        output.write_text("new transcript")
        old = self.root / "EP001-test.md"
        old.write_text("old cloud transcript" * 100)
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "muapi"}):
            with patch.object(batch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, str(output) + "\n", "")) as run:
                actual = batch.transcribe_episode(str(self.audio), str(self.root), {"num": 1, "title": "test"}, provider="local")
        self.assertEqual(actual, str(output))
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--provider") + 1], "local")
        self.assertEqual(command[command.index("--model") + 1], "small")
        self.assertNotEqual(actual, str(old))

    def test_batch_forwards_cloud_identity_and_failures_return_none(self):
        batch = load_script("batch_transcribe")
        result = subprocess.CompletedProcess([], 1, "", "secret-key")
        with patch.object(batch.subprocess, "run", return_value=result) as run:
            self.assertIsNone(batch.transcribe_episode(str(self.audio), str(self.root), {}, provider="atlas", model="some/model", base_url="https://endpoint.example/api/v1", state_dir=self.state, language="en", resubmit=True))
        command = run.call_args.args[0]
        for flag, value in [("--provider", "atlas"), ("--model", "some/model"), ("--base-url", "https://endpoint.example/api/v1"), ("--state-dir", str(self.state)), ("--language", "en")]:
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("--resubmit", command)

    def test_explicit_local_cli_works_without_any_cloud_key_and_keeps_previous_output(self):
        import types
        transcribe = load_script("transcribe")
        segment = types.SimpleNamespace(start=0, end=1, text="local transcript")
        whisper = types.SimpleNamespace(WhisperModel=lambda *args, **kwargs: types.SimpleNamespace(transcribe=lambda *args, **kwargs: ([segment], None)))
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "muapi"}), patch.dict(sys.modules, {"faster_whisper": whisper}):
            self.assertEqual(transcribe.main([str(self.audio), str(self.root), "--provider", "local"]), 0)
            outputs = list(self.root.glob("*.md"))
            self.assertEqual(len(outputs), 1)
            outputs[0].write_text("user changes")
            self.assertEqual(transcribe.main([str(self.audio), str(self.root), "--provider", "local"]), 0)
        self.assertEqual(len(list(self.root.glob("*.md"))), 2)
        self.assertEqual(outputs[0].read_text(), "user changes")

    def test_ambiguous_crash_marker_and_active_lock_block_duplicate_post(self):
        import fcntl
        with patch.object(cloud, "request_json", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_atlas()
        state = json.loads(next(self.state.glob("*.json")).read_text())
        self.assertEqual(state["status"], "submitting")
        with patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "resubmit"):
                self.run_atlas()
            request.assert_not_called()
            with next(self.state.glob("*.lock")).open("r+") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, "already running"):
                    self.run_atlas(resubmit=True)
                request.assert_not_called()

    def test_audio_changed_during_preparation_never_submits_paid_job(self):
        original_prepare = cloud.CloudProvider.prepare
        def changed(client, audio_path, deadline):
            payload = original_prepare(client, audio_path, deadline)
            self.audio.write_bytes(b"changed while preparing")
            return payload
        with patch.object(cloud.CloudProvider, "prepare", changed), patch.object(cloud, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "changed"):
                self.run_atlas()
            request.assert_not_called()

    def test_config_defaults_are_portable_and_environment_free_when_explicit(self):
        config_module = load_script("provider_config")
        with patch.dict(os.environ, {"PODCAST_TRANSCRIBE_PROVIDER": "muapi", "MUAPI_BASE_URL": "https://other.example/v1"}):
            config = config_module.resolve_provider_config(provider="local", state_dir=self.state)
            self.assertEqual(config["provider"], "local")
            self.assertEqual(config["base_url"], "")
            self.assertEqual(config["model"], "small")
            explicit = config_module.resolve_provider_config(provider="muapi", base_url="https://stable.example/v1", state_dir=self.state)
            self.assertEqual(explicit["base_url"], "https://stable.example/v1")
        self.assertNotIn("key", json.dumps(config).lower())

    def test_cloud_export_keeps_full_text_when_timestamp_segment_is_invalid(self):
        transcribe = load_script("transcribe")
        original_sibling = transcribe._sibling
        output = self.root / "full-text.md"
        responses = [{"url": "https://storage.example/audio"}, {"request_id": "mu-id"}, {"status": "completed", "output": {"text": "第一句。第二句。", "segments": [{"start": 0, "end": 1, "text": "第一句。"}, {"start": None, "end": None, "text": "第二句。"}]}}]
        with patch.object(transcribe, "_sibling", side_effect=lambda name: cloud if name == "cloud_transcribe" else original_sibling(name)), patch.object(cloud, "request_json", side_effect=responses):
            transcribe.transcribe_audio(str(self.audio), str(output), "Full text", provider="muapi", state_dir=self.state)
        text = output.read_text()
        self.assertIn("第一句。第二句。", text)
        self.assertIn("时间戳参考", text)

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
            self.assertEqual(transcribe.main(["https://public.example/episode/1", str(self.root), "--provider", "muapi", "--state-dir", str(self.state)]), 1)
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


if __name__ == "__main__":
    unittest.main()
