"""기존 DB에 저장된 RSS 기사의 HTML 덩어리를 정리하는 일회성 스크립트.

rss.py 에 _strip_html 이 추가되기 이전 수집된 기사들은 description 에
<table><img> 같은 HTML 이 그대로 저장되어 있다. 분류기·프론트에 영향을
주므로 동일 정리 로직을 DB 에 소급 적용한다.

실행: PYTHONPATH=. python scripts/clean_rss_html.py
"""

import asyncio
import sys

from sqlalchemy import select, update

from backend.collectors.rss import _strip_html
from backend.database import async_session
from backend.database.models import Article


async def main():
    cleaned = 0
    skipped = 0
    async with async_session() as db:
        stmt = select(Article).where(Article.source_api == "rss")
        result = await db.execute(stmt)
        rows = result.scalars().all()
        for art in rows:
            updates: dict = {}
            if art.description and "<" in art.description:
                new_desc = _strip_html(art.description)
                if new_desc != art.description:
                    updates["description"] = new_desc
            if art.content and "<" in art.content:
                new_content = _strip_html(art.content)
                if new_content != art.content:
                    updates["content"] = new_content
            if updates:
                await db.execute(
                    update(Article).where(Article.id == art.id).values(**updates)
                )
                cleaned += 1
            else:
                skipped += 1
        await db.commit()

    print(f"cleaned={cleaned}, skipped={skipped}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
