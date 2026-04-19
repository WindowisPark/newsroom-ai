# 참고 문헌 · 설계 근거

> 파이프라인 · UX 설계 결정의 학계/업계 근거. 각 항목은 **핵심 주장**과 **우리 시스템의 반영 지점**을 병기한다. PT 발표에서 "감 아니라 근거 기반 설계" 서사로 활용.

---

## 1. RAG (Retrieval-Augmented Generation) — 초안 생성의 근거

### 1-1. A Survey on Retrieval And Structuring Augmented Generation (2025)
- **URL**: https://arxiv.org/pdf/2509.10697
- **핵심 주장**: 기본 RAG(단순 top-k 검색)로는 production 품질 미달. 메타데이터 인식 검색·Recency bias·Reranking·Citation 강제·Evaluation 루프가 필요.
- **우리 반영**:
  - `drafter._retrieve_references()` — 키워드 매칭 + **recency 가중** (published_at 90일 내 우선) + **reranking** (매칭 수 0.6 + recency 0.4)
  - `DraftOut.references[]` — 인용 원천을 구조화해 반환

### 1-2. DRAGUN Track @ TREC 2025
- **URL**: https://arxiv.org/html/2603.23125
- **핵심 주장**: 신뢰 가능한 뉴스를 위해 (a) 비판·조사형 질문 생성 (b) **investigative report 를 retrieval-augmented 로 생성해 독자가 신뢰도 판단**에 활용. "투명한 근거"가 핵심.
- **우리 반영**:
  - DraftDialog 에 **"참고한 자사 기사 ▼"** 접힘 패널 — 어떤 출처를 읽고 썼는지 UI 상 투명 공개
  - `DRAFT_SYSTEM` 프롬프트에 "원문에 없는 사실 추측 금지 + 유보적 표현" 강제

### 1-3. RAG in Modern Journalism (Cajic, 2024)
- **URL**: https://www.dinocajic.com/retrieval-augmented-generation-news/
- **핵심 주장**: "Standalone LLM은 할루시네이션 위험 — 정확성·신뢰가 중요한 뉴스룸에선 retrieval layer 로 근거 grounding 필수". 실제 구현 권고: "Use only the provided sources; cite each claim; if evidence is missing, say you don't know."
- **우리 반영**:
  - `DRAFT_SYSTEM` 본문에 위 3원칙 직접 명시
  - Pydantic `DraftOut` 검증으로 LLM 할루시네이션·포맷 이탈 조기 차단

### 1-4. RAG Evaluation Survey 2025
- **URL**: https://arxiv.org/html/2504.14891v1
- **핵심 주장**: RAG 품질 평가 지표는 faithfulness(근거 충실도) · answer relevance · context precision/recall 등 다축. 현재는 통합 평가 체계 미성숙.
- **우리 반영**:
  - 평가는 PT 대상 기능 밖이지만, 추후 확장 포인트로 문서에 기록
  - `DraftOut.references[]` + `sources[]` 구조가 추후 faithfulness 자동 측정의 기반이 됨

---

## 2. Style Consistency — 스타일 앵커(C)의 근거와 한계

### 2-1. How Examples Improve LLM Style Consistency (Latitude, 2024)
- **URL**: https://latitude.so/blog/how-examples-improve-llm-style-consistency
- **핵심 주장**: Few-shot 예시는 zero-shot 대비 일관되게 품질·스타일 정렬을 개선. LLM이 패턴 인식·복제로 동작하므로 "명확한 템플릿"이 주어지면 ambiguity가 감소.
- **우리 반영**:
  - `DRAFT_SYSTEM` 에 **톤 샘플 1건 (lead 300자)** 을 추가 주입 — "few-shot" 원리 적용
  - 건수는 1~2건으로 제한 (토큰 부담 ↓)

### 2-2. Catch Me If You Can? LLMs Still Struggle to Imitate Implicit Writing Styles (arxiv 2509.14543, 2025)
- **URL**: https://arxiv.org/html/2509.14543v1
- **핵심 주장**: 2025년 기준 최신 LLM도 일상 작가의 **암묵적** 문체를 완벽히 재현하지 못함. Few-shot 으로 어느 정도 향상되나 한계 명확.
- **우리 반영**:
  - **기대치 조정**: "서울신문 톤 완벽 재현"이 아니라 "일반 LLM 보고체 → 국내 종합지 어조로 nudge" 수준으로 포지셔닝
  - PT 화법: "완벽 모방은 아니지만 자사 톤에 가깝게 유도하는 앵커" — 과장 금지

### 2-3. A Recipe For Arbitrary Text Style Transfer with LLMs (ACL 2022)
- **URL**: https://aclanthology.org/2022.acl-short.94.pdf
- **핵심 주장**: LLM에 스타일 전이는 훈련 없이 in-context 예시만으로 가능. 예시 선택(target 스타일 표본)이 품질 핵심 변수.
- **우리 반영**:
  - 스타일 앵커 선정 기준: **동일 카테고리의 최근 서울신문 기사 1건** — 주제 무관, 카테고리 일치로 문체 정합성 확보

### 2-4. Conversation Style Transfer using Few-Shot Learning (Amazon Science)
- **URL**: https://assets.amazon.science/2e/13/09db2e194e01ac743a2767b5c703/conversation-style-transfer-using-few-shot-learning.pdf
- **핵심 주장**: Few-shot prior sample이 zero-shot 대비 target author 문체에 더 정렬된 출력 생성.
- **우리 반영**: 상동 (2-1 과 같은 근거로 스타일 앵커 1건 채택)

---

## 3. 파이프라인 품질 개선 — Tier 1/2/3 근거

### 3-1. Cross-source Consensus as Editorial Signal
- **관행 기반**: 편집국 실무에서 "주요 이슈"는 단일 기사 중요도가 아니라 **다수 매체의 교차 보도**로 판단 (Agenda-Setting Theory — McCombs & Shaw, 1972).
- **우리 반영**:
  - `_boost_by_frequency` 를 DB-wide(오늘 기준)로 확장, **키워드별 고유 매체 수**로 가중
  - 속보 조건: `importance_score >= 8.5 AND source_count >= 2`

### 3-2. Category Alignment in NLP Pipelines
- **일반 원칙**: 분류 스키마를 단일 원천(single source of truth)으로 관리해 프롬프트·DB·UI 이탈 방지. 특히 `Literal` 기반 검증이 LLM 출력 정규화를 강제.
- **우리 반영**:
  - `schemas.py` 의 `Category` Literal 이 단일 원천, `CATEGORIES` tuple 을 프롬프트에 f-string 주입
  - `_CATEGORY_ALIASES` 로 LLM 변이(science → tech 등) 정규화

---

## 4. 활용 예정 확장 (미구현)

### 4-1. Hierarchical Long Text Style Transfer (arxiv 2505.07888)
- **URL**: https://arxiv.org/html/2505.07888v1
- **내용**: 문장·단락 두 레벨에서 스타일 전이하는 계층적 프레임워크.
- **판단**: 과제 스코프 초과. 본 초안은 단일 프롬프트·단일 LLM 호출 단순 구조로 충분. 추후 장문 기획기사·사설 자동화 시 검토.

### 4-2. Retrieval-style In-context Learning (TACL)
- **URL**: https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00697/124630/Retrieval-style-In-context-Learning-for-Few-shot
- **내용**: Few-shot 분류에서 retrieval 기반 demonstration 선택이 성능 개선.
- **판단**: 현재 분류기(Haiku)는 충분히 성능이 좋아 적용 불요. 분류 정확도 저하 시 재검토.

---

## 5. 인용 표기 원칙

- PT 슬라이드·README 에서 **"왜 이렇게 설계했는가"** 를 설명할 때 본 문서의 URL을 직접 링크하거나 bullet으로 요약 인용.
- 모든 참고 자료는 **public URL** 만 사용 (사내 문서·유료 자료 없음).
- 검색 시점은 2026-04 기준. 추가 인용은 이 파일에 append.
