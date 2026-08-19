"""SenseVoice-Small 转录统一封装：延迟加载模型、依赖体检、统一耗时统计。

funasr / torch 只在真正需要转录时才 import，保持轻量安装模式可用。
"""

import sys
import time

from chubby_common import deps

SENSEVOICE_MODEL = "iic/SenseVoiceSmall"


def transcribe(audio_path: str, language: str = "auto") -> tuple:
    """用 SenseVoice-Small 转录音频，返回 (text, elapsed_seconds)。

    模型在首次调用时加载（延迟 import funasr），缺依赖时给出安装提示。
    """
    deps.ensure_funasr()
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    print("  🎙️  Loading model...", file=sys.stderr)
    model = AutoModel(
        model=SENSEVOICE_MODEL,
        trust_remote_code=True,
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
    )

    print("  🎙️  Transcribing...", file=sys.stderr)
    start = time.time()
    result = model.generate(
        input=audio_path, language=language, use_itn=True, batch_size_s=60
    )
    elapsed = time.time() - start

    text = ""
    if result:
        for record in result:
            if "text" in record:
                text += rich_transcription_postprocess(record["text"]) + "\n\n"

    print(f"  ✅ Done in {elapsed:.1f}s", file=sys.stderr)
    return text.strip(), elapsed
