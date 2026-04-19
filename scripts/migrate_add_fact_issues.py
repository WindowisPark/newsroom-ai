"""일회성 마이그레이션 — article_drafts.fact_issues 컬럼 추가.

Base.metadata.create_all 은 신규 테이블만 만들고 기존 테이블에 컬럼을
추가하지 않으므로, 기존 article_drafts 테이블에 fact_issues JSONB 컬럼을
수동으로 추가한다. 이미 존재하면 skip.

실행: PYTHONPATH=. python scripts/migrate_add_fact_issues.py
"""

import asyncio
import sys

from sqlalchemy import text

from backend.database import engine


SQL_CHECK = """
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'article_drafts' AND column_name = 'fact_issues';
"""

SQL_ADD = """
ALTER TABLE article_drafts
ADD COLUMN fact_issues JSONB NOT NULL DEFAULT '[]'::jsonb;
"""


async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text(SQL_CHECK))
        existing = result.scalar_one_or_none()
        if existing:
            print("fact_issues 컬럼 이미 존재 — skip", file=sys.stderr)
            return
        await conn.execute(text(SQL_ADD))
        print("fact_issues 컬럼 추가 완료", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
