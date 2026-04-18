"""Anthropic API 클라이언트 - Haiku/Sonnet 라우팅"""

import json
import logging

from anthropic import AsyncAnthropic

from backend.config import get_settings

logger = logging.getLogger(__name__)

# ── 모델 선정 ──
# Haiku 4.5: 빠르고 저렴. 구조화 JSON 출력, 단순 분류/요약에 최적.
# Sonnet 4.6: 다중 문서 교차 추론, 이중 언어 프레임 비교 등 복잡 분석에 사용.
HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

# 작업별 모델 매핑 — 각 파이프라인 단계의 복잡도에 맞춰 배치
MODEL_FOR = {
    "classify":     HAIKU_MODEL,   # 1차 분류: 단일 기사 → 카테고리/키워드/감성 (단순, 대량)
    "agenda":       SONNET_MODEL,  # 의제 도출: 50건 교차 분석 → top N 이슈 (복잡 추론)
    "perspective":  SONNET_MODEL,  # 관점 비교: 한/영 프레임 차이 분석 (이중 언어 맥락)
    "briefing":     HAIKU_MODEL,   # 브리핑 생성: 정리된 데이터 → 역피라미드 작문 (단순 요약)
    "headline":     HAIKU_MODEL,   # 헤드라인 추천: 제목 3개 생성 (단순 생성)
    "timeline":     SONNET_MODEL,  # 타임라인: 과거 사건 recall + 맥락 추론 (지식 필요)
}

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
