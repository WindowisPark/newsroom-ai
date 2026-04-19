"""자동 팩트 검증 — L2 Detection layer (docs/REFERENCES.md §4 참조)

3개 검증기를 병렬 실행:
  1. Entity KB — 공직자 직책 불일치 (role_mismatch)
  2. Number grounding — 숫자·금액·퍼센트·연도가 원문 기사에 실재하는지 (number_unsupported)
  3. Entity grounding — 인명·지명이 원문 기사에 등장하는지 (entity_unsupported)

한계 (정직한 인정):
  - 근사값·단위변환(1만 달러 vs $10,000)은 false positive 가능
  - KB 에 없는 인물은 검증 불가 (entity_unknown 플래그로만)
  - 인과관계·뉘앙스는 자동 검출 불가 (human review 에 위임)

각 Issue 는 'acknowledged' 로 편집자가 개별 확인 처리 가능 (HITL).
"""

from __future__ import annotations

import re
import uuid as _uuid
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Literal

import yaml
from pydantic import BaseModel, Field


IssueSeverity = Literal["high", "medium", "low"]
IssueKind = Literal[
    "role_mismatch",       # Entity KB 직책 불일치 (high)
    "number_unsupported",  # 원문에 없는 수치 (medium)
    "entity_unsupported",  # 원문에 없는 인명/지명 (low~medium)
    "entity_unknown",      # KB 미등재 인물이 직책과 함께 등장 (low)
]


class FactIssue(BaseModel):
    """검증 경고 단위.

    acknowledged 필드는 편집실 UI 에서 개별 확인 시 true 가 된다.
    high-severity 경고가 모두 ack 되어야 in_review → approved 전이 허용.
    """
    id: str = Field(default_factory=lambda: str(_uuid.uuid4()))
    severity: IssueSeverity
    kind: IssueKind
    claim: str                        # 문제되는 표현 원문
    evidence: str | None = None       # 올바른 정보 or 근거 부재 설명
    span_text: str | None = None      # 본문 내 해당 문장 일부
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None
    acknowledged_note: str | None = None


# ── Entity KB 로딩 ──

_KB_PATH = Path(__file__).resolve().parent.parent / "facts" / "entity_kb.yaml"


@lru_cache(maxsize=1)
def _load_kb() -> list[dict]:
    if not _KB_PATH.exists():
        return []
    with _KB_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("entities", [])


# 주요 직책 어휘 — LLM 생성문에서 "{name} {role}" 패턴 추출용
_ROLE_VOCAB = [
    "대통령", "전 대통령", "국무총리", "총리", "부총리",
    "장관", "차관", "국회의장", "대법원장",
    "국회의원", "의원", "당 대표", "대표",
    "시장", "도지사", "구청장", "군수",
    "정책실장", "수석",
]


def _extract_role_claims(text: str) -> list[tuple[str, str]]:
    """본문에서 (name, role) 쌍 추출. 단순 substring 검색 기반."""
    claims: list[tuple[str, str]] = []
    for ent in _load_kb():
        name = ent["name"]
        if name not in text:
            continue
        # name 뒤 5자 이내에 role 어휘가 있는지
        for match in re.finditer(re.escape(name), text):
            tail = text[match.end() : match.end() + 10]
            for role in _ROLE_VOCAB:
                if tail.startswith(role) or tail.lstrip().startswith(role):
                    claims.append((name, role))
                    break
    return claims


def _check_entity_kb(text: str) -> list[FactIssue]:
    """생성문의 (인물, 직책) 쌍을 KB 의 current_role 과 대조."""
    issues: list[FactIssue] = []
    kb = {e["name"]: e for e in _load_kb()}
    for name, role in _extract_role_claims(text):
        entry = kb.get(name)
        if not entry:
            continue
        correct = entry.get("current_role", "")
        # '전 대통령' 같은 경우 'current_role: 전 대통령' 이라 role="대통령" 과 불일치하므로 flag (의도적)
        if role != correct and not (role == "대통령" and correct == "대통령"):
            # role 이 correct 의 일부이거나(예: '의원' ⊂ '국회의원') 반대면 관용 매칭
            if role in correct or correct in role:
                continue
            issues.append(FactIssue(
                severity="high",
                kind="role_mismatch",
                claim=f"{name} {role}",
                evidence=f"{name}의 현재 직책은 '{correct}'" +
                         (f" ({entry.get('affiliation')})" if entry.get("affiliation") else ""),
                span_text=_find_sentence(text, f"{name} {role}"),
            ))
    return issues


# ── Number grounding ──

_NUMBER_PATTERN = re.compile(
    r"(?<![0-9a-zA-Z,\.])"                # 숫자 앞에 숫자/영문 없음
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)" # 본체 (콤마 포함 or 소수)
    r"\s*"
    r"(만|천|억|조|%|퍼센트|원|달러|명|건|년|월|일|개|곳|%|kg|g|km|m)?"
)


def _extract_numbers(text: str) -> list[str]:
    """본문에서 의미있는 수치 표현 추출 — '1만', '60만 원', '2.5%', '2026년' 등."""
    results = []
    for m in _NUMBER_PATTERN.finditer(text):
        number = m.group(1).replace(",", "")
        unit = m.group(2) or ""
        # 너무 흔한 수치(예: 1, 2, 3 단일 자리) 는 noise 라 제외 — 2자리 이상만
        if len(number) < 2 and not unit:
            continue
        results.append((number, unit, m.group(0)))
    return results


def _text_contains_number(source_text: str, number: str, unit: str) -> bool:
    """원문 전체 텍스트에 동일 수치가 있는지 — 단위와 함께 or 단독.

    완전 일치 + 단위 변형(1만 = 10000) 약간 허용.
    """
    if not source_text:
        return False
    # 단순 완전 일치
    if unit and f"{number}{unit}" in source_text.replace(" ", ""):
        return True
    if unit and f"{number} {unit}" in source_text:
        return True
    if number in source_text:
        # 숫자만 일치해도 pass (약한 검증) — false positive 최소화
        return True
    # '1만' ↔ '10000' 단위 변환 간이 허용
    if unit == "만":
        try:
            expanded = str(int(number) * 10000)
            if expanded in source_text.replace(",", ""):
                return True
        except ValueError:
            pass
    return False


def _check_numbers(text: str, source_corpus: str) -> list[FactIssue]:
    """생성문의 숫자가 원문 corpus 에 존재하지 않으면 flag."""
    issues: list[FactIssue] = []
    seen: set[str] = set()
    for number, unit, raw in _extract_numbers(text):
        key = f"{number}{unit}"
        if key in seen:
            continue
        seen.add(key)
        if not _text_contains_number(source_corpus, number, unit):
            issues.append(FactIssue(
                severity="medium",
                kind="number_unsupported",
                claim=raw,
                evidence="원문 기사에 동일 수치가 없습니다",
                span_text=_find_sentence(text, raw),
            ))
    return issues


# ── Entity grounding ──

_ENTITY_PATTERN = re.compile(
    r"([가-힣]{2,4}(?:대통령|총리|장관|의원|대표|시장|지사))"
)


def _check_entity_grounding(text: str, source_corpus: str) -> list[FactIssue]:
    """본문에 등장하는 '{이름}{직책}' 형태가 원문에 동일 이름이 있는지 체크.

    KB 에 등록된 인물은 _check_entity_kb 가 처리. 여기는 KB 미등재 인물 중
    원문에도 없는 경우(완전 허구 생성) 를 잡는다.
    """
    issues: list[FactIssue] = []
    kb_names = {e["name"] for e in _load_kb()}
    seen: set[str] = set()
    for m in _ENTITY_PATTERN.finditer(text):
        full = m.group(1)
        # name 부분 추출: 끝 2~3자 역할 분리
        for role in ["대통령", "총리", "장관", "의원", "대표", "시장", "지사"]:
            if full.endswith(role):
                name = full[: -len(role)]
                break
        else:
            continue
        if not name or name in kb_names or name in seen:
            continue
        seen.add(name)
        if name not in source_corpus:
            issues.append(FactIssue(
                severity="low",
                kind="entity_unknown",
                claim=full,
                evidence=f"'{name}'이(가) 원문 기사와 KB 어디에도 등장하지 않습니다",
                span_text=_find_sentence(text, full),
            ))
    return issues


# ── 헬퍼 ──

def _find_sentence(text: str, fragment: str) -> str | None:
    """fragment 를 포함한 문장(. 또는 줄바꿈 단위)을 반환 — UI 하이라이트용."""
    if fragment not in text:
        return None
    idx = text.find(fragment)
    # 앞 경계
    candidates_start = [0]
    p = text.rfind(". ", 0, idx)
    if p != -1:
        candidates_start.append(p + 2)
    n = text.rfind("\n", 0, idx)
    if n != -1:
        candidates_start.append(n + 1)
    start = max(candidates_start)
    # 뒤 경계
    candidates_end = [len(text)]
    p2 = text.find(". ", idx)
    if p2 != -1:
        candidates_end.append(p2 + 1)
    n2 = text.find("\n", idx)
    if n2 != -1:
        candidates_end.append(n2)
    # 한글 문장 마지막 "."(공백 없는 종결) 도 고려
    p3 = text.find(".", idx)
    if p3 != -1 and p3 > idx + len(fragment) - 1:
        candidates_end.append(p3 + 1)
    end = min(candidates_end)
    return text[start:end].strip()


def _build_source_corpus(source_articles: list[dict] | list) -> str:
    """원문 기사들을 하나의 큰 텍스트로 합쳐 grounding 검증 대상으로 사용."""
    parts: list[str] = []
    for a in source_articles:
        if hasattr(a, "title"):  # Article ORM
            parts.append(a.title or "")
            parts.append(a.description or "")
            parts.append(a.content or "")
        elif isinstance(a, dict):
            parts.append(a.get("title", ""))
            parts.append(a.get("description", ""))
            parts.append(a.get("content", ""))
    return "\n".join(p for p in parts if p)


# ── 공개 API ──

def verify_text(text: str, source_corpus: str = "") -> list[FactIssue]:
    """임의 텍스트에 대해 3종 검증 실행."""
    issues: list[FactIssue] = []
    issues.extend(_check_entity_kb(text))
    if source_corpus:
        issues.extend(_check_numbers(text, source_corpus))
        issues.extend(_check_entity_grounding(text, source_corpus))
    return issues


def verify_article_draft(
    title: str,
    lead: str,
    body: str,
    background: str,
    source_articles: Iterable,
) -> list[FactIssue]:
    """ArticleDraft 전체(제목+리드+본문+배경)를 검증.

    source_articles: origin_article_ids 로 조회된 Article ORM 또는 dict 들.
    KB 검증은 corpus 무관, grounding 검증은 corpus 기반.
    """
    combined = "\n".join([title, lead, body, background])
    corpus = _build_source_corpus(list(source_articles))
    return verify_text(combined, corpus)
