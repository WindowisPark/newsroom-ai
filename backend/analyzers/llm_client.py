"""Anthropic API 클라이언트 - Haiku/Sonnet 라우팅"""

import json
import logging

from anthropic import AsyncAnthropic

from backend.config import get_settings

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6-20250514"

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


async def call_llm(
    system_prompt: str,
    user_message: str,
    model: str = SONNET_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> dict:
    """LLM 호출 후 JSON 파싱된 결과 반환

    Returns:
        {"content": dict, "prompt_tokens": int, "completion_tokens": int}
    """
    client = get_client()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text

    # JSON 추출 (코드 블록 안에 있을 수 있음)
    content = _parse_json(raw_text)

    if content.get("parse_error"):
        logger.error(f"LLM JSON 파싱 실패 (model={model}): {raw_text[:200]}")
        raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {raw_text[:100]}")

    return {
        "content": content,
        "prompt_tokens": response.usage.input_tokens,
        "completion_tokens": response.usage.output_tokens,
        "model_used": model,
    }


def _parse_json(text: str) -> dict:
    """텍스트에서 JSON 추출"""
    # 직접 파싱 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 코드 블록에서 추출
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 중괄호 범위로 추출
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return {"raw_text": text, "parse_error": True}
