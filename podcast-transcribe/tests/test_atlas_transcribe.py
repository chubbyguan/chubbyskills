import base64
import json
import pathlib
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock


SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import atlas_transcribe


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class AtlasTranscribeTests(unittest.TestCase):
    def test_transcribe_file_submits_once_then_polls(self):
        responses = [
            FakeResponse({"code": 200, "data": {"id": "prediction-1", "status": "created"}}),
            FakeResponse({
                "code": 200,
                "data": {
                    "id": "prediction-1",
                    "status": "completed",
                    "stt_result": {"text": "测试转录文本"},
                },
            }),
        ]

        with tempfile.NamedTemporaryFile(suffix=".mp3") as audio_file:
            audio_file.write(b"fake-audio")
            audio_file.flush()

            with mock.patch.object(
                atlas_transcribe.urllib.request,
                "urlopen",
                side_effect=responses,
            ) as urlopen:
                transcript = atlas_transcribe.transcribe_file(
                    audio_file.name,
                    api_key="test-key",
                    timeout=1,
                )

        self.assertEqual(transcript, "测试转录文本")
        self.assertEqual(urlopen.call_count, 2)

        submit_request = urlopen.call_args_list[0].args[0]
        self.assertEqual(submit_request.get_method(), "POST")
        self.assertTrue(submit_request.full_url.endswith("/model/generateAudio"))
        payload = json.loads(submit_request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "bytedance/seed-asr-2.0")
        self.assertEqual(payload["audio_url"], base64.b64encode(b"fake-audio").decode("ascii"))
        self.assertEqual(payload["format"], "mp3")

        poll_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(poll_request.get_method(), "GET")
        self.assertTrue(poll_request.full_url.endswith("/model/prediction/prediction-1"))

    def test_completed_submission_does_not_poll(self):
        response = FakeResponse({
            "code": 200,
            "data": {"status": "completed", "outputs": ["ready immediately"]},
        })

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(b"fake-audio")
            audio_file.flush()

            with mock.patch.object(
                atlas_transcribe.urllib.request,
                "urlopen",
                return_value=response,
            ) as urlopen:
                transcript = atlas_transcribe.transcribe_file(
                    audio_file.name,
                    api_key="test-key",
                )

        self.assertEqual(transcript, "ready immediately")
        self.assertEqual(urlopen.call_count, 1)

    def test_failed_prediction_raises_clear_error(self):
        response = FakeResponse({
            "code": 200,
            "data": {"status": "failed", "error": "unsupported audio"},
        })

        with mock.patch.object(
            atlas_transcribe.urllib.request,
            "urlopen",
            return_value=response,
        ):
            with self.assertRaisesRegex(RuntimeError, "unsupported audio"):
                atlas_transcribe.wait_for_transcription(
                    "prediction-1",
                    api_key="test-key",
                    timeout=1,
                    poll_interval=0,
                )

    def test_submission_failure_is_not_retried(self):
        error = urllib.error.HTTPError(
            "https://api.atlascloud.ai/api/v1/model/generateAudio",
            503,
            "service unavailable",
            hdrs=None,
            fp=None,
        )

        with tempfile.NamedTemporaryFile(suffix=".mp3") as audio_file:
            audio_file.write(b"fake-audio")
            audio_file.flush()

            with mock.patch.object(
                atlas_transcribe.urllib.request,
                "urlopen",
                side_effect=error,
            ) as urlopen:
                with self.assertRaises(urllib.error.HTTPError):
                    atlas_transcribe.submit_transcription(
                        audio_file.name,
                        api_key="test-key",
                    )

        self.assertEqual(urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
