"""Qwen3-ASR-0.6B 本地转录后端（可选重依赖，延迟加载）。

不属于默认安装；需要时自行安装：
    pip install qwen-asr transformers torch
"""

import sys
import time

QWEN_MODEL = "Qwen/Qwen3-ASR-0.6B"

_LANGUAGES = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean", "yue": "Cantonese"}


def _ensure_qwen_asr() -> None:
    import importlib.util
    try:
        spec = importlib.util.find_spec("qwen_asr")
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        print("❌ 缺少 Python 依赖 `qwen_asr`。", file=sys.stderr)
        print("   请安装：pip install qwen-asr transformers torch", file=sys.stderr)
        print("   装完后重新运行本脚本。", file=sys.stderr)
        raise SystemExit(1)


def transcribe(audio_path: str, language: str = "auto") -> tuple:
    """用 Qwen3-ASR-0.6B（transformers 后端，CPU float32）转录，返回 (text, elapsed_seconds)。"""
    _ensure_qwen_asr()
    import torch
    from qwen_asr import Qwen3ASRModel

    print("  🎙️  Loading model...", file=sys.stderr)
    model = Qwen3ASRModel.from_pretrained(
        QWEN_MODEL,
        dtype=torch.float32,
        device_map="cpu",
        max_inference_batch_size=4,
        # qwen-asr 默认的 max_new_tokens 会截断长音频；5 分钟中文对话需要 4096 才完整。
        max_new_tokens=4096,
    )

    print("  🎙️  Transcribing...", file=sys.stderr)
    start = time.time()
    results = model.transcribe(audio=audio_path, language=_LANGUAGES.get(language))
    elapsed = time.time() - start

    text = ""
    if results:
        text = "\n\n".join(record.text.strip() for record in results if getattr(record, "text", "").strip())

    print(f"  ✅ Done in {elapsed:.1f}s", file=sys.stderr)
    return text.strip(), elapsed
