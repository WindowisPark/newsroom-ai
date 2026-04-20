import { memo } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DraftDialog } from "@/components/draft-dialog";
import { CATEGORY_LABEL } from "@/lib/labels";
import { isHighImportance } from "@/lib/importance";
import { relativeTime } from "@/lib/time";
import type { Article } from "@/lib/types";

// 기사 리스트의 단일 행. 뉴스 flat list · 카테고리 섹션 · 대시보드 최신 뉴스에서 공용.
// showDraft=false 로 대시보드처럼 좁은 영역에선 초안 버튼 숨김.
function ArticleRowComponent({
  article,
  showDraft = true,
}: {
  article: Article;
  showDraft?: boolean;
}) {
  const isHigh = isHighImportance(article);
  return (
    <Card
      size="sm"
      className={
        isHigh
          ? "border-l-4 border-l-primary bg-primary/5 transition-colors"
          : "transition-colors hover:bg-muted/40"
      }
    >
      <CardContent>
        <div className="flex items-start justify-between gap-4">
          <Link
            href={`/news/${article.id}`}
            className="flex-1 min-w-0 block hover:text-primary"
          >
            <div className="flex items-center gap-1.5">
              {isHigh && (
                <AlertTriangle
                  className="size-3.5 text-primary shrink-0"
                  aria-label="중요 기사"
                />
              )}
              <p className="font-medium leading-snug line-clamp-1">{article.title}</p>
            </div>
            <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
              {article.description}
            </p>
            <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
              <span>{article.source_name}</span>
              <span>{relativeTime(article.published_at)}</span>
            </div>
          </Link>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            {isHigh && (
              <Badge className="text-[10px] bg-primary/10 text-primary border-primary/30">
                중요
              </Badge>
            )}
            {article.analysis?.category && (
              <Badge variant="secondary" className="text-[10px]">
                {CATEGORY_LABEL[article.analysis.category] || article.analysis.category}
              </Badge>
            )}
            {showDraft && (
              <DraftDialog
                articleIds={[article.id]}
                topicHint={article.title}
                triggerLabel="초안"
                triggerSize="sm"
                triggerVariant="outline"
              />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export const ArticleRow = memo(ArticleRowComponent);
