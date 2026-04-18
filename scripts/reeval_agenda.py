"""개선된 analyze_agenda 를 원샷으로 실행하여 이전 결과와 비교.

새 AgendaReport 를 DB 에 추가 기록하고 핵심 지표를 stdout 으로 출력한다.
"""

import asyncio
import json
import sys
from datetime import date

from sqlalchemy import select

from backend.analyzers.agenda import analyze_agenda
from backend.database import async_session
from backend.database.models import AgendaReport


async def main():
    today = date.today()

    async with async_session() as db:
        # 개선 적용 후 의제 재생성
        print("[re-eval] analyze_agenda 실행 중...", file=sys.stderr)
        new_report = await analyze_agenda(db, today)

        # 오늘자 AgendaReport 전체 조회 (최신순)
        stmt = (
            select(AgendaReport)
            .where(AgendaReport.date == today)
            .order_by(AgendaReport.generated_at.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()

        summary = []
        for r in rows:
            issues = r.top_issues or []
            avg_src = (
                sum(i.get("source_count", 0) for i in issues) / len(issues)
                if issues else 0
            )
            avg_art = (
                sum(i.get("article_count", 0) for i in issues) / len(issues)
                if issues else 0
            )
            summary.append({
                "generated_at": r.generated_at.isoformat(),
                "model": r.model_used,
                "top_n": len(issues),
                "avg_source_count": round(avg_src, 2),
                "avg_article_count": round(avg_art, 2),
                "multi_source_ratio": round(
                    sum(1 for i in issues if i.get("source_count", 0) >= 2) / len(issues),
                    2,
                ) if issues else 0,
                "top_issues": [
                    {
                        "rank": i.get("rank"),
                        "topic": i.get("topic"),
                        "article_count": i.get("article_count"),
                        "source_count": i.get("source_count"),
                        "importance_score": i.get("importance_score"),
                    }
                    for i in issues
                ],
            })

        print(json.dumps({"reports": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
