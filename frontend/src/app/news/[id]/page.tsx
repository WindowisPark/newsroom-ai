"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  ExternalLink,
  Clock,
  Building2,
  User,
  MapPin,
  Tag,
} from "lucide-react";
import { getNewsDetail } from "@/lib/api";
import type { Article } from "@/lib/types";
import { CopyButton } from "@/components/copy-button";
import { DraftDialog } from "@/components/draft-dialog";

const categoryLabel: Record<string, string> = {
  politics: "정치", economy: "경제", society: "사회",
  world: "국제", tech: "기술", culture: "문화", sports: "스포츠",
};

const sentimentLabel: Record<string, string> = {
  positive: "긍정", negative: "부정", neutral: "중립",
};

const entityIcon: Record<string, typeof User> = {
  person: User,
  organization: Building2,
  location: MapPin,
};

function buildArticleSnippet(article: Article): string {
  const pub = article.published_at
    ? new Date(article.published_at).toLocaleString("ko-KR")
    : "발행일 미상";
  const lines = [
    article.title,
    `${article.source_name} · ${pub}`,
  ];
  if (article.description) lines.push("", article.description);
  lines.push("", article.url);
  return lines.join("\n");
}

export default function NewsDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await getNewsDetail(id);
        setArticle(res.data);
      } catch {
        setError("기사를 불러올 수 없습니다.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="space-y-4">
        <Link href="/news">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="size-4" /> 뉴스 목록
          </Button>
        </Link>
        <p className="text-muted-foreground">{error || "기사를 찾을 수 없습니다."}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link href="/news">
        <Button variant="ghost" size="sm">
          <ArrowLeft className="size-4" /> 뉴스 목록
        </Button>
      </Link>

      <div>
        <h1 className="text-2xl font-bold leading-tight">{article.title}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span>{article.source_name}</span>
          <span>{article.source_type === "domestic" ? "국내" : "해외"}</span>
          <span className="flex items-center gap-1">
            <Clock className="size-3" />
            {new Date(article.published_at).toLocaleString("ko-KR")}
          </span>
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-primary hover:underline"
          >
            원문 보기 <ExternalLink className="size-3" />
          </a>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <CopyButton
            value={buildArticleSnippet(article)}
            label="복사"
            variant="outline"
          />
          <DraftDialog
            articleIds={[article.id]}
            topicHint={article.title}
            triggerLabel="이 기사로 초안 작성"
          />
        </div>
      </div>

      {/* Analysis info */}
      {article.analysis && (
        <Card>
          <CardHeader>
            <CardTitle>AI 분석</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">
                {categoryLabel[article.analysis.category] || article.analysis.category}
              </Badge>
              <Badge variant={article.analysis.sentiment === "positive" ? "default" : article.analysis.sentiment === "negative" ? "destructive" : "outline"}>
                {sentimentLabel[article.analysis.sentiment]}
              </Badge>
              <Badge variant="outline">
                중요도 {article.analysis.importance_score.toFixed(1)}/10
              </Badge>
            </div>

            {article.analysis.keywords.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <Tag className="size-3" /> 키워드
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {article.analysis.keywords.map((kw) => (
                    <Badge key={kw} variant="secondary" className="text-xs">{kw}</Badge>
                  ))}
                </div>
              </div>
            )}

            {article.analysis.entities.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">엔티티</p>
                <div className="flex flex-wrap gap-1.5">
                  {article.analysis.entities.map((ent) => {
                    const Icon = entityIcon[ent.type] || Tag;
                    return (
                      <Badge key={ent.name} variant="outline" className="text-xs gap-1">
                        <Icon className="size-3" /> {ent.name}
                      </Badge>
                    );
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Article body */}
      <div className="prose prose-sm max-w-none dark:prose-invert">
        {article.description && (
          <p className="text-base font-medium text-foreground leading-relaxed">
            {article.description}
          </p>
        )}
        {article.content && (
          <div className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-foreground/80">
            {article.content}
          </div>
        )}
      </div>
    </div>
  );
}
