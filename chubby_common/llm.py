"""LLM 输出容错工具：解析模型返回的 JSON / 数值，失败时给出可读错误而非裸崩。

采集/加工类工具的原则：任何一步失败都要给出可读提示并尽量降级。
"""

import json
import re


def parse_json_response(raw: str) -> dict:
    """容错解析 LLM 返回的 JSON：去代码块包裹，非法时提取最外层对象。"""
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 二次尝试：模型可能在 JSON 前后加了杂散文本
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise RuntimeError(
            "模型返回的不是合法 JSON，请重试。"
            f"原始内容：{raw[:200]}"
        )


def safe_int(value, default: int = 3) -> int:
    """模型输出的整数可能不是数字，兜底到默认值。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
