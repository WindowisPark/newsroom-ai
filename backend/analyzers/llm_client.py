"""Anthropic API 클라이언트 - Haiku/Sonnet 라우팅"""

import json
import logging

from anthropic import AsyncAnthropic, APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings

logger = logging.getLogger(__name__)


# Anthropic API 일시 장애 대응: 연결/타임아웃/429/5xx 는 지수 백오프로 3회 재시도.
# 4xx(인증·스키마 오류)는 재시도해도 동일 실패이므로 대상에서 제외.
_RETRYABLE_EXCEPTIONS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)


def _should_retry(exc: BaseException) -> bool:
    """재시도 대상 판별 — 일시 장애(연결/타임아웃/429/5xx)만 재시도."""
    if isinstance(exc, _RETRYABLE_EXCEPTIONS):
        return True
    if isinstance(exc, APIStatusError):
        return 500 <= getattr(exc, "status_code", 0) < 600
    return False

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
    "draft":        SONNET_MODEL,  # 기사 초안: 다중 기사 교차 + 역피라미드 + 6하원칙 (복잡 작문)
}

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_should_retry),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _messages_create_with_retry(client: AsyncAnthropic, **kwargs):
    """Anthropic messages.create 를 재시도 래핑 — 일시 장애에만 지수 백오프 3회."""
    return await client.messages.create(**kwargs)


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
    response = await _messages_create_with_retry(
        client,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text
    stop_reason = getattr(response, "stop_reason", None)

    # JSON 추출 (코드 블록 안에 있을 수 있음)
    content = _parse_json(raw_text)

    if content.get("parse_error"):
        logger.error(
            f"LLM JSON 파싱 실패 (model={model}, stop_reason={stop_reason}, "
            f"len={len(raw_text)}): head={raw_text[:200]!r} tail={raw_text[-200:]!r}"
        )
        if stop_reason == "max_tokens":
            raise ValueError(
                f"LLM 응답이 max_tokens({max_tokens})에서 잘렸습니다. max_tokens 상향 필요."
            )
        raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {raw_text[:100]}")

    return {
        "content": content,
        "prompt_tokens": response.usage.input_tokens,
        "completion_tokens": response.usage.output_tokens,
        "model_used": model,
    }


def _parse_json(text: str) -> dict:
    """텍스트에서 JSON 추출 — 코드펜스/설명 텍스트 래핑 대응."""
    candidates: list[str] = []

    stripped = text.strip()

    # 1) 원문 그대로
    candidates.append(stripped)

    # 2) ```json ... ``` 또는 ``` ... ``` 코드펜스 안쪽 (닫는 펜스 없어도 OK)
    if stripped.startswith("```"):
        body = stripped
        first_nl = body.find("\n")
        if first_nl > 0:
            body = body[first_nl + 1 :]
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3]
        candidates.append(body.strip())

    # 3) 첫 `{` ~ 마지막 `}` 범위
    start = stripped.find("{")
    end = stripped.rfind("}") + 1
    if start != -1 and end > start:
        candidates.append(stripped[start:end])

    # strict=False: Sonnet 이 body Markdown 에 이스케이프 안 된 raw 개행을 섞는
    # 경우가 있어 허용. JSON 표준 위반이지만 모델 출력 현실 수용.
    for c in candidates:
        try:
            return json.loads(c, strict=False)
        except json.JSONDecodeError:
            continue

    return {"raw_text": text, "parse_error": True}
