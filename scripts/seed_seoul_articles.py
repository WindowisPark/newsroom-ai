"""서울신문 시연용 샘플 시드 — RAG 참조 코퍼스 확보.

실제 서울신문 RSS 수집이 불안정하거나 초기 DB에 자사 기사가 없을 때
PT 시연 안정성을 위해 샘플 10~20건을 DB 에 source_name='서울신문' 으로 삽입한다.

각 샘플은 실제 보도 패턴을 모사한 **가상 콘텐츠**다 (저작권 회피).
카테고리 다양성(politics/economy/world/society/tech)을 확보해 톤 앵커 후보로도 쓰인다.

실행: PYTHONPATH=. python scripts/seed_seoul_articles.py
중복 방지: URL 기반. 이미 존재하면 skip.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from backend.database import async_session
from backend.database.models import Article, ArticleAnalysis


# 시연용 서울신문 샘플 (허구 · 저작권 회피). 카테고리 다양성 확보.
# published_at 은 최근 30~80일 범위로 분산 — recency 가중 효과 검증용.
_SAMPLES: list[dict] = [
    {
        "title": "중동 긴장 고조 속 원유 시장 변동성 확대…정부, 비축유 점검",
        "description": "중동 지역 지정학적 긴장 고조로 국제유가가 배럴당 90달러를 재차 넘어서자 산업통상자원부가 전략비축유 운용 상황을 긴급 점검했다.",
        "category": "economy",
        "keywords": ["중동 긴장", "국제유가", "비축유", "산업통상자원부"],
        "days_ago": 7,
    },
    {
        "title": "미·이란, 호르무즈 해협 통제권 놓고 외교 공방",
        "description": "미국과 이란이 호르무즈 해협의 통항 안전과 군사적 억지를 둘러싸고 공개 외교전에 돌입했다. 한국은 해당 해협을 통한 원유 수송 의존도가 높아 촉각을 세우고 있다.",
        "category": "world",
        "keywords": ["호르무즈 해협", "미국", "이란", "외교", "원유 수송"],
        "days_ago": 14,
    },
    {
        "title": "정치개혁법 국회 법사위 통과…광역 비례대표 확대 논의",
        "description": "정치개혁법안이 국회 법제사법위원회를 통과했다. 광역 비례대표 확대와 중대선거구제 도입이 핵심 쟁점으로, 여야 간 절충안 조율이 본회의 처리의 변수로 떠오른다.",
        "category": "politics",
        "keywords": ["정치개혁", "광역 비례대표", "중대선거구제", "법사위"],
        "days_ago": 3,
    },
    {
        "title": "AI 기본법 시행령 초안 공개…개인정보보호 강화 조항 포함",
        "description": "과학기술정보통신부가 AI 기본법 시행령 초안을 공개했다. 개인정보보호와 알고리즘 투명성 확보 조항이 포함되어 산업계 의견 수렴이 진행 중이다.",
        "category": "tech",
        "keywords": ["AI 기본법", "시행령", "개인정보보호", "알고리즘 투명성"],
        "days_ago": 20,
    },
    {
        "title": "소상공인 대출 연체율 9년 만 최고…금융당국 모니터링 강화",
        "description": "소상공인 대출 연체율이 9년 만에 최고 수준을 기록했다. 금융당국은 고금리 장기화에 따른 상환 부담 증가를 원인으로 지목하고 모니터링을 강화한다고 밝혔다.",
        "category": "economy",
        "keywords": ["소상공인 대출", "연체율", "금융당국", "고금리"],
        "days_ago": 10,
    },
    {
        "title": "서울 지하철 심야 연장 운행 확대 검토…시민 편의 vs 유지보수 균형",
        "description": "서울시가 주요 노선 심야 연장 운행 확대를 검토한다. 시민 편의 증진과 지하철 유지보수 시간 확보 사이의 균형이 과제로 지목된다.",
        "category": "society",
        "keywords": ["서울 지하철", "심야 연장 운행", "서울시", "유지보수"],
        "days_ago": 5,
    },
    {
        "title": "기후변화 대응 탄소세 인상안 국회 상정…산업계 반발",
        "description": "정부가 기후변화 대응을 위한 탄소세 인상안을 국회에 상정했다. 제조업·발전업계는 비용 부담 급증을 우려하며 단계적 도입을 주장하고 있다.",
        "category": "politics",
        "keywords": ["탄소세", "기후변화", "제조업", "단계 도입"],
        "days_ago": 25,
    },
    {
        "title": "K-콘텐츠 수출 역대 최대…드라마·웹툰 동반 성장",
        "description": "올해 상반기 K-콘텐츠 수출액이 역대 최대치를 기록했다. 드라마·웹툰·음악 전 장르가 동반 성장하며 제조업 수출 둔화를 상쇄하는 효자 품목으로 자리잡았다.",
        "category": "culture",
        "keywords": ["K-콘텐츠", "수출", "드라마", "웹툰"],
        "days_ago": 30,
    },
    {
        "title": "전기차 배터리 재활용 시장 본격 개화…규제 정비 숙제",
        "description": "전기차 배터리 재활용 시장이 본격 개화 조짐을 보이며 관련 투자가 급증하고 있다. 다만 폐배터리 분류·수거·처리 규제 정비가 시급한 과제로 지목된다.",
        "category": "tech",
        "keywords": ["전기차 배터리", "재활용", "폐배터리", "규제"],
        "days_ago": 40,
    },
    {
        "title": "남북 접경지역 긴장 고조…군 당국 경계 태세 상향",
        "description": "남북 접경지역에서 군사적 긴장이 고조되자 군 당국이 경계 태세를 상향 조정했다. 합참은 북한군 이동 동향을 예의주시하고 있다고 밝혔다.",
        "category": "politics",
        "keywords": ["남북 접경", "군사 긴장", "합참", "경계 태세"],
        "days_ago": 2,
    },
    {
        "title": "코스피 2.5% 급락…외국인 매도세 중동 불안 영향",
        "description": "코스피가 외국인 매도세로 2.5% 급락했다. 중동 지정학 리스크와 달러 강세가 복합 작용하며 안전자산 선호 심리가 확산된 것으로 분석된다.",
        "category": "economy",
        "keywords": ["코스피", "외국인 매도", "중동 리스크", "달러 강세"],
        "days_ago": 1,
    },
    {
        "title": "청년 주거 정책 개편안 발표…월세 세액공제 확대",
        "description": "국토교통부가 청년 주거 정책 개편안을 발표했다. 월세 세액공제 한도 확대와 기숙사형 임대주택 공급 확대가 주요 내용이다.",
        "category": "society",
        "keywords": ["청년 주거", "월세 세액공제", "임대주택", "국토교통부"],
        "days_ago": 16,
    },
    {
        "title": "반도체 수출 회복세 지속…메모리 가격 상승 영향",
        "description": "반도체 수출이 3개월 연속 증가세를 이어갔다. 메모리 반도체 가격 상승과 AI 서버용 고부가가치 제품 수요 확대가 주효했다.",
        "category": "economy",
        "keywords": ["반도체 수출", "메모리", "AI 서버", "고부가가치"],
        "days_ago": 12,
    },
    {
        "title": "온라인 플랫폼 규제법 국회 재발의…공정위 집행력 강화",
        "description": "온라인 플랫폼 규제법이 국회에 재발의됐다. 공정거래위원회의 조사·제재 권한을 강화하는 조항이 쟁점이 될 전망이다.",
        "category": "politics",
        "keywords": ["온라인 플랫폼", "규제법", "공정거래위원회", "제재"],
        "days_ago": 22,
    },
    {
        "title": "초고령사회 진입 임박…간병·요양 인프라 확충 시급",
        "description": "한국이 내년 초고령사회 진입을 앞둔 가운데 간병·요양 인프라 확충이 시급한 과제로 부상했다. 전문가들은 공적 돌봄 체계 재설계를 주문한다.",
        "category": "society",
        "keywords": ["초고령사회", "간병", "요양", "공적 돌봄"],
        "days_ago": 45,
    },
]


async def main():
    inserted = 0
    skipped = 0
    async with async_session() as db:
        for i, sample in enumerate(_SAMPLES):
            url = f"https://www.seoul.co.kr/news/sample/{i+1:04d}"

            existing = (await db.execute(
                select(Article).where(Article.url == url)
            )).scalar_one_or_none()
            if existing:
                skipped += 1
                continue

            published = datetime.now(timezone.utc) - timedelta(days=sample["days_ago"])

            article = Article(
                id=uuid4(),
                title=sample["title"],
                description=sample["description"],
                content=sample["description"],  # 샘플은 본문도 description 으로 재사용
                url=url,
                source_name="서울신문",
                source_type="domestic",
                source_api="seed",
                published_at=published,
                collected_at=datetime.now(timezone.utc),
            )
            db.add(article)
            await db.flush()

            analysis = ArticleAnalysis(
                article_id=article.id,
                category=sample["category"],
                keywords=sample["keywords"],
                entities=[],
                sentiment="neutral",
                importance_score=6.5,
                analyzed_at=datetime.now(timezone.utc),
                model_used="seed-v1",
            )
            db.add(analysis)
            inserted += 1

        await db.commit()

    print(f"seeded={inserted}, skipped={skipped}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
