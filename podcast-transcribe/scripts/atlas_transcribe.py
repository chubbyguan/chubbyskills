#!/usr/bin/env python3
"""Atlas Cloud speech-to-text client for the podcast transcription skill."""

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_BASE_URL = "https://api.atlascloud.ai/api/v1"
DEFAULT_MODEL = "bytedance/seed-asr-2.0"
RETRYABLE_GET_STATUS = {429, 500, 502, 503, 504}


def _response_data(payload: dict) -> dict:
    code = payload.get("code")
    if code not in (None, 0, 200, "200"):
        message = payload.get("message") or payload.get("msg") or "unknown error"
        raise RuntimeError(f"Atlas Cloud API error ({code}): {message}")

    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise RuntimeError("Atlas Cloud returned an invalid response payload")
    return data


def _request_json(request: urllib.request.Request, timeout: float) -> dict:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Atlas Cloud returned a non-object response")
    return payload


def _extract_transcript(data: dict) -> str:
    stt_result = data.get("stt_result")
    if isinstance(stt_result, dict):
        text = stt_result.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

    outputs = data.get("outputs")
    if isinstance(outputs, list) and outputs:
        text = outputs[0]
        if isinstance(text, str) and text.strip():
            return text.strip()

    raise RuntimeError("Atlas Cloud completed without transcript text")


def submit_transcription(
    audio_path: str,
    api_key: str,
    language: str = "",
    base_url: str = DEFAULT_BASE_URL,
) -> dict:
    """Submit one transcription request. The POST is intentionally not retried."""
    with open(audio_path, "rb") as audio_file:
        encoded_audio = base64.b64encode(audio_file.read()).decode("ascii")

    audio_format = audio_path.rsplit(".", 1)[-1].lower()
    if audio_format not in {"mp3", "wav", "ogg", "raw"}:
        raise ValueError(f"Unsupported Atlas audio format: {audio_format}")

    payload = {
        "model": DEFAULT_MODEL,
        "audio_url": encoded_audio,
        "format": audio_format,
        "enable_itn": True,
        "enable_punc": True,
        "show_utterances": False,
    }
    if language:
        payload["language"] = language

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/model/generateAudio",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    return _response_data(_request_json(request, timeout=60))


def wait_for_transcription(
    request_id: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 1800,
    poll_interval: float = 3,
) -> str:
    """Poll a submitted transcription with bounded retries for GET requests."""
    deadline = time.monotonic() + timeout
    delay = max(0.0, poll_interval)
    url = f"{base_url.rstrip('/')}/model/prediction/{urllib.parse.quote(request_id)}"

    while time.monotonic() < deadline:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        try:
            data = _response_data(_request_json(request, timeout=30))
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_GET_STATUS:
                raise RuntimeError(f"Atlas Cloud polling failed with HTTP {exc.code}") from exc
        else:
            status = str(data.get("status", "")).lower()
            if status in {"completed", "succeeded"}:
                return _extract_transcript(data)
            if status in {"failed", "timeout", "canceled", "cancelled"}:
                error = data.get("error") or data.get("message") or status
                raise RuntimeError(f"Atlas Cloud transcription failed: {error}")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(delay, remaining))
        delay = min(max(delay * 1.5, 1.0), 10.0)

    raise TimeoutError(f"Atlas Cloud transcription timed out after {timeout:.0f}s")


def transcribe_file(
    audio_path: str,
    api_key: str,
    language: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 1800,
) -> str:
    """Submit an audio file once, then poll until transcript text is available."""
    submitted = submit_transcription(
        audio_path=audio_path,
        api_key=api_key,
        language=language,
        base_url=base_url,
    )
    status = str(submitted.get("status", "")).lower()
    if status in {"completed", "succeeded"}:
        return _extract_transcript(submitted)

    request_id = submitted.get("id")
    if not isinstance(request_id, str) or not request_id:
        raise RuntimeError("Atlas Cloud submission did not return a prediction ID")

    return wait_for_transcription(
        request_id=request_id,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )
