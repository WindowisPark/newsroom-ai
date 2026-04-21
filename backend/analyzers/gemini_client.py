"""Google Gemini 클라이언트 - Gemini 3 Flash 라우팅

초안 품질 판독(이종 judge)용. Anthropic(Sonnet/Haiku) 이 생성한 결과를
다른 회사 모델이 독립 판정하여 self-critique 편향을 피한다.
"""

import json
import logging

from google import genai
from google.genai import types
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings

logger = logging.getLogger(__name__)


# 과제 허용 모델 중 판독용: gemini 3 flash preview
# (gemini 3.1 flash lite preview 는 판단 정교함 부족)
GEMINI_JUDGE_MODEL = "gemini-3-flash-preview"


_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        key = get_settings().gemini_api_key
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY 가 설정되지 않았습니다. .env 또는 fly secrets 확인."
            )
        _client = genai.Client(api_key=key)
    return _client


def _should_retry(exc: BaseException) -> bool:
    """재시도 대상 — 네트워크·타임아웃·429·5xx. 인증·스키마 오류는 즉시 실패."""
    msg = str(exc).lower()
    if any(k in msg for k in ("timeout", "connection", "unavailable", "deadline")):
        return True
    # google-genai 는 상태코드를 예외 속성으로 제공 — code 또는 status_code 둘 다 체크
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and (code == 429 or 500 <= code < 600):
        return True
    return False


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_should_retry),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _generate_with_retry(
    client: genai.Client,
    model: str,
    contents: str,
    config: types.GenerateContentConfig,
):
    # google-genai 는 비동기 aio 인터페이스 제공
    return await client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


async def call_gemini(
    system_prompt: str,
    user_message: str,
    model: str = GEMINI_JUDGE_MODEL,
    max_output_tokens: int = 2048,
    temperature: float = 0.2,
    response_schema: dict | None = None,
) -> dict:
    """Gemini 호출 + JSON 파싱된 결과 반환.

    response_schema 를 주면 Structured Output 모드(application/json)로 동작 →
    스키마 위반 확률 대폭 감소. 스키마 없으면 일반 JSON 응답.

    Returns:
        {"content": dict, "prompt_tokens": int, "completion_tokens": int, "model_used": str}
    """
    client = get_client()

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json",
    )
    if response_schema is not None:
        config.response_schema = response_schema

    response = await _generate_with_retry(
        client, model=model, contents=user_message, config=config
    )

    raw_text = response.text or ""
    try:
        content = json.loads(raw_text)
    except json.JSONDecodeError:
        # 코드펜스 래핑된 경우만 한 번 더 시도 (Gemini 는 structured mode 에서 거의 없음)
        stripped = raw_text.strip()
        if stripped.startswith("```"):
            body = stripped
            first_nl = body.find("\n")
            if first_nl > 0:
                body = body[first_nl + 1 :]
            if body.rstrip().endswith("```"):
                body = body.rstrip()[:-3]
            try:
                content = json.loads(body.strip())
            except json.JSONDecodeError:
                content = None
        else:
            content = None

        if content is None:
            finish_reason = getattr(response.candidates[0], "finish_reason", None) if getattr(response, "candidates", None) else None
            logger.error(
                f"Gemini JSON 파싱 실패 (model={model}, finish_reason={finish_reason}, "
                f"len={len(raw_text)}): head={raw_text[:200]!r} tail={raw_text[-200:]!r}"
            )
            raise ValueError(
                f"Gemini 응답을 JSON으로 파싱할 수 없습니다: {raw_text[:100]}"
            )

    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
    completion_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

    return {
        "content": content,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "model_used": model,
    }
