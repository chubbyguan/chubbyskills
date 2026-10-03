"""Resumable optional cloud ASR providers (DashScope qwen3-asr-flash, Groq Whisper), using standard-library HTTPS only.

Earlier Atlas/MuAPI experimental adapters were adapted from PR #3 by @binyangzhu000-sudo
and PR #5 by @Anil-matcha; they have been superseded by the DashScope and Groq backends.
The persistent lifecycle, authentication boundaries and cache are shared here.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid


def _config_module():
    spec = importlib.util.spec_from_file_location("podcast_provider_config", Path(__file__).with_name("provider_config.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoRedirect(HTTPRedirectHandler):
    """Never replay API keys or upload bodies to a redirect target."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(request: Request, timeout: float) -> dict:
    # Use our own opener so global/proxy handlers cannot re-enable redirects.
    with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        content = response.read(16 * 1024 * 1024 + 1)
    if len(content) > 16 * 1024 * 1024:
        raise RuntimeError("Cloud response exceeds 16 MiB")
    payload = json.loads(content.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Cloud returned an invalid response object")
    return payload


def _atomic_json(path: Path, value: dict) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError("Unsafe cloud state file")
    fd, temporary = tempfile.mkstemp(prefix=".podcast-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # Persist the rename before any next potentially billable network action.
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _job_lock(path: Path):
    import fcntl
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("This cloud job is already running; wait and retry") from None
        yield
    finally:
        os.close(descriptor)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _remaining(deadline: float, maximum: float = 30) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Cloud operation timeout")
    return min(maximum, remaining)


def _data(payload: dict) -> dict:
    if payload.get("code") not in (None, 0, 200, "200"):
        raise RuntimeError("Cloud API returned a failure code")
    return payload


def _nested(payload, keys):
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if isinstance(payload.get(key), str) and payload[key]:
            return payload[key]
    for key in ("data", "output"):
        found = _nested(payload.get(key), keys)
        if found:
            return found
    return None


def _transcript(payload) -> dict | None:
    if isinstance(payload, str) and payload.strip():
        return {"text": payload.strip(), "segments": []}
    if isinstance(payload, list):
        text = " ".join(item["text"].strip() for item in payload if isinstance(item, dict) and isinstance(item.get("text"), str))
        return _transcript({"text": text, "segments": payload}) if text else None
    if not isinstance(payload, dict):
        return None
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        segments = []
        for segment in payload.get("segments", []) if isinstance(payload.get("segments", []), list) else []:
            if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
                continue
            try:
                start = float(segment.get("start", 0))
                end = float(segment.get("end", start))
            except (TypeError, ValueError):
                continue
            if math.isfinite(start) and math.isfinite(end) and 0 <= start <= end:
                segments.append({"start": start, "end": end, "text": segment["text"].strip()})
        return {"text": text.strip(), "segments": segments}
    outputs = payload.get("outputs")
    if isinstance(outputs, list) and outputs and isinstance(outputs[0], str) and outputs[0].strip():
        return {"text": outputs[0].strip(), "segments": []}
    for key in ("stt_result", "output", "output_data", "data"):
        found = _transcript(payload.get(key))
        if found:
            return found
    return None


DASHSCOPE_MIME_TYPES = {
    "mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "aac": "audio/aac",
    "flac": "audio/flac", "ogg": "audio/ogg", "opus": "audio/ogg",
}

# Base64 inflates payloads by 4/3; keep the raw file small enough that the encoded
# data URL stays below the documented 10 MB input limit of qwen3-asr-flash.
DASHSCOPE_MAX_AUDIO_BYTES = 7 * 1024 * 1024

GROQ_FORMATS = {"flac", "mp3", "mp4", "mpeg", "mpga", "m4a", "ogg", "wav", "webm"}

# Groq's free tier accepts files up to 25 MB; anything at or above is refused before upload.
GROQ_MAX_AUDIO_BYTES = 25 * 1024 * 1024


def _convert_to_mp3(audio_path: Path, deadline: float, label: str) -> bytes:
    """Convert an unsupported container with ffmpeg and return MP3 bytes."""
    with tempfile.TemporaryDirectory(prefix=f"podcast-{label}-") as temporary:
        converted = Path(temporary) / "audio.mp3"
        try:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(audio_path), "-codec:a", "libmp3lame", str(converted)], capture_output=True, check=True, timeout=_remaining(deadline, 1800))
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError(f"{label} container conversion requires working ffmpeg") from None
        return converted.read_bytes()


def _multipart(fields: dict, filename: str, content: bytes) -> tuple:
    boundary = "----chubbyskills-" + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    # Fixed safe multipart filename avoids leaking paths or injecting headers.
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(parts)


class CloudProvider:
    """Synchronous cloud ASR: DashScope qwen3-asr-flash or Groq whisper-large-v3-turbo."""

    KEY_ENVS = {"dashscope": "DASHSCOPE_API_KEY", "groq": "GROQ_API_KEY"}

    def __init__(self, config: dict):
        self.config = config
        self.provider = config["provider"]
        self.base_url = config["base_url"]
        self.model = config["model"]
        self.language = config["language"]
        key_hint = self.KEY_ENVS[self.provider]
        key = os.environ.get(key_hint) or ""
        self.auth_header = "Authorization"
        self.auth_value = f"Bearer {key}" if key else ""
        if not key:
            raise ValueError(f"Cloud provider requires {key_hint}")
        if any(ord(char) < 32 or ord(char) == 127 for char in key):
            raise ValueError(f"Invalid {key_hint}")

    def request(self, endpoint, deadline, payload=None, *, body=None, content_type=None):
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            content_type = "application/json"
        headers = {self.auth_header: self.auth_value}
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(f"{self.base_url}/{endpoint}", data=body, headers=headers, method="POST" if body is not None else "GET")
        return request_json(request, _remaining(deadline))

    def submit(self, payload, deadline):
        if self.provider == "groq":
            boundary, body = _multipart(payload["fields"], payload["filename"], payload["content"])
            response = self.request("audio/transcriptions", deadline, body=body, content_type=f"multipart/form-data; boundary={boundary}")
        else:
            response = self.request("chat/completions", deadline, payload)
            # qwen3-asr-flash returns the transcript in the chat completion response.
            choices = response.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise RuntimeError("DashScope returned an invalid completion response")
            message = choices[0].get("message")
            text = message.get("content") if isinstance(message, dict) else None
            if isinstance(text, list):
                text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
            response = {"text": text, "segments": []}
        text = response.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"{self.provider} completed without transcript text")
        result = {"status": "completed", "text": text.strip()}
        if isinstance(response.get("segments"), list):
            result["segments"] = response["segments"]
        return result

    def poll(self, task_id, deadline):
        raise RuntimeError(f"{self.provider} transcription is synchronous and has no polling endpoint")

    def prepare(self, audio_path: Path, deadline: float) -> dict:
        if self.provider == "groq":
            return self._prepare_groq(audio_path, deadline)
        return self._prepare_dashscope(audio_path, deadline)

    def _prepare_dashscope(self, audio_path: Path, deadline: float) -> dict:
        audio_format = audio_path.suffix.lower().lstrip(".")
        if audio_format not in DASHSCOPE_MIME_TYPES:
            # Convert in a private temporary directory; hash identity stays on original input.
            content = _convert_to_mp3(audio_path, deadline, "dashscope")
            audio_format, mime = "mp3", DASHSCOPE_MIME_TYPES["mp3"]
            raw_size = len(content)
        else:
            mime = DASHSCOPE_MIME_TYPES[audio_format]
            raw_size = audio_path.stat().st_size
            if raw_size > DASHSCOPE_MAX_AUDIO_BYTES:
                raise ValueError(
                    "音频超过 DashScope qwen3-asr-flash 的输入上限（base64 编码后不超过 10MB，"
                    "且仅支持不超过 5 分钟的录音）；请改用本地 SenseVoice-Small（--provider local）转录长播客")
            content = audio_path.read_bytes()
        if raw_size > DASHSCOPE_MAX_AUDIO_BYTES:
            raise ValueError(
                "音频超过 DashScope qwen3-asr-flash 的输入上限（base64 编码后不超过 10MB，"
                "且仅支持不超过 5 分钟的录音）；请改用本地 SenseVoice-Small（--provider local）转录长播客")
        data_url = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": [
                {"type": "input_audio", "input_audio": {"data": data_url, "format": audio_format}},
            ]}],
            "stream": False,
            "asr_options": {"enable_itn": True},
        }
        if self.language:
            payload["asr_options"]["language"] = self.language
        return payload

    def _prepare_groq(self, audio_path: Path, deadline: float) -> dict:
        audio_format = audio_path.suffix.lower().lstrip(".")
        if audio_format not in GROQ_FORMATS:
            # Convert in a private temporary directory; hash identity stays on original input.
            content = _convert_to_mp3(audio_path, deadline, "groq")
            audio_format = "mp3"
        else:
            if audio_path.stat().st_size >= GROQ_MAX_AUDIO_BYTES:
                raise ValueError(
                    "音频达到 Groq 免费层 25MB 文件上限；请改用本地 SenseVoice-Small（--provider local）转录长播客")
            content = audio_path.read_bytes()
        if len(content) >= GROQ_MAX_AUDIO_BYTES:
            raise ValueError(
                "音频达到 Groq 免费层 25MB 文件上限；请改用本地 SenseVoice-Small（--provider local）转录长播客")
        fields = {"model": self.model, "response_format": "verbose_json"}
        if self.language and self.language != "auto":
            # Groq expects an ISO-639-1 code such as zh/en.
            fields["language"] = self.language
        return {"fields": fields, "filename": f"audio.{audio_format}", "content": content}


def transcribe_cloud(audio_path, *, provider, model=None, language=None, base_url=None,
                     state_dir=None, cloud_timeout=1800, poll_interval=3, resubmit=False) -> dict:
    """Return normalized transcript; an interrupted paid job is resumed, never silently resubmitted."""
    settings = _config_module()
    config = settings.resolve_provider_config(provider, model, language, base_url, state_dir)
    if config["provider"] == "local":
        raise ValueError("Cloud transcription requires dashscope or groq")
    cloud_timeout = settings.positive_seconds(cloud_timeout, "cloud-timeout")
    poll_interval = settings.positive_seconds(poll_interval, "poll-interval", maximum=60)
    audio_path = Path(audio_path)
    if not audio_path.is_file() or audio_path.stat().st_size == 0:
        raise ValueError("Audio input must be a nonempty regular file")
    identity = {"provider": config["provider"], "model": config["model"], "language": config["language"], "base_url": config["base_url"], "audio_sha256": _file_hash(audio_path)}
    cache_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    state_dir = Path(config["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path = state_dir / f"{cache_key}.json"
    deadline = time.monotonic() + cloud_timeout
    with _job_lock(state_dir / f"{cache_key}.lock"):
        state = None
        if state_path.exists() or state_path.is_symlink():
            if state_path.is_symlink() or not state_path.is_file():
                raise RuntimeError("Unsafe cloud state file")
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if not isinstance(state, dict) or state.get("identity") != identity:
                    raise ValueError("State identity mismatch")
            except (ValueError, OSError):
                raise RuntimeError("Cloud state is invalid; inspect the state file before retrying to avoid duplicate billing") from None
        if resubmit and state:
            history = state_dir / "history"
            history.mkdir(exist_ok=True, mode=0o700)
            _atomic_json(history / f"{cache_key}-{uuid.uuid4().hex}.json", state)
            state = None
        if state:
            if state.get("status") == "completed":
                result = state.get("result")
                if not isinstance(result, dict) or not isinstance(result.get("text"), str) or not result["text"].strip():
                    raise RuntimeError("Completed cloud state is invalid; inspect it before retrying")
                return dict(result, provider=config["provider"], model=config["model"], cached=True)
            if state.get("status") != "pending" or not isinstance(state.get("task_id"), str) or not state["task_id"]:
                raise RuntimeError("Cloud job is ambiguous or failed; check provider billing/status, then use --resubmit only to explicitly create a new billable job")
        client = CloudProvider(config)
        if state is None:
            payload = client.prepare(audio_path, deadline)
            if _file_hash(audio_path) != identity["audio_sha256"]:
                raise RuntimeError("Audio changed during preparation; no transcription job was submitted")
            # Written before POST: process death / lost response can never trigger an automatic duplicate POST.
            state = {"version": 1, "identity": identity, "status": "submitting", "created_at": time.time()}
            _atomic_json(state_path, state)
            try:
                submitted = client.submit(payload, deadline)
                # Save any returned task ID before validating other response fields.
                task_id = _nested(submitted, ("id", "request_id", "task_id"))
                if task_id:
                    state.update(status="pending", task_id=task_id)
                    _atomic_json(state_path, state)
                data = _data(submitted)
                status = (_nested(data, ("status",)) or "").lower()
                if not task_id and status not in {"completed", "succeeded", "success"}:
                    raise RuntimeError("Submission did not return a task ID")
                if status in {"completed", "succeeded", "success"}:
                    result = _transcript(data)
                    if result is None:
                        raise RuntimeError("Completed cloud response has no transcript")
                    state.update(status="completed", result=result)
                    _atomic_json(state_path, state)
                    return dict(result, provider=config["provider"], model=config["model"], cached=False)
            except Exception:
                if state.get("status") == "submitting":
                    state["status"] = "ambiguous"
                    _atomic_json(state_path, state)
                raise RuntimeError("Cloud submission outcome is ambiguous or response processing failed; state saved. Retry resumes a saved task ID; otherwise inspect provider status before --resubmit") from None
        while True:
            try:
                response = client.poll(state["task_id"], deadline)
                data = _data(response)
                status = (_nested(data, ("status",)) or "").lower()
                if status in {"completed", "succeeded", "success"}:
                    result = _transcript(data)
                    if result is None:
                        raise RuntimeError("Completed cloud response has no transcript")
                    state.update(status="completed", result=result)
                    _atomic_json(state_path, state)
                    return dict(result, provider=config["provider"], model=config["model"], cached=False)
                if status in {"failed", "error", "timeout", "cancelled", "canceled"}:
                    state["status"] = "failed"
                    _atomic_json(state_path, state)
                    raise RuntimeError("Cloud task failed; inspect provider status before --resubmit")
                if status not in {"pending", "queued", "processing", "starting", "in_queue", "running", "created"}:
                    raise RuntimeError("Cloud returned an unrecognized job status")
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise RuntimeError(f"Cloud polling failed with HTTP {exc.code}; task ID saved for retry") from None
            except (URLError, TimeoutError, OSError):
                # Stop rather than hide network failure; next command resumes GET with the same ID.
                raise RuntimeError("Cloud polling interrupted or timed out; task ID saved for retry") from None
            except (ValueError, RuntimeError):
                raise RuntimeError("Cloud polling failed; task state saved. Retry resumes GET unless task failed; inspect provider status before --resubmit") from None
            try:
                time.sleep(min(poll_interval, _remaining(deadline)))
            except TimeoutError:
                raise RuntimeError("Cloud polling timed out; task ID saved for retry") from None
