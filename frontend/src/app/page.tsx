"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Newspaper,
  TrendingUp,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  Clock,
} from "lucide-react";
import { getNews, getAgenda, getTrends, getHealth } from "@/lib/api";
import type { Article, AgendaData, TrendData, HealthData } from "@/lib/types";

const sentimentColor = {
  positive: "bg-emerald-100 text-emerald-700",
  negative: "bg-red-100 text-red-700",
  neutral: "bg-zinc-100 text-zinc-700",
} as const;

const categoryLabel: Record<string, string> = {
  politics: "정치",
  economy: "경제",
  society: "사회",
  world: "국제",
  tech: "기술",
  culture: "문화",
  sports: "스포츠",
};

export default function DashboardPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [agenda, setAgenda] = useState<AgendaData | null>(null);
  const [trends, setTrends] = useState<TrendData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [newsRes, agendaRes, trendsRes, healthRes] = await Promise.allSettled([
        getNews({ limit: "5", sort_by: "published_at" }),
        getAgenda({ top_n: "5" }),
        getTrends({ period: "24h", type: "keyword" }),
        getHealth(),
      ]);
      if (newsRes.status === "fulfilled") setArticles(newsRes.value.data);
      if (agendaRes.status === "fulfilled") setAgenda(agendaRes.value.data);
      if (trendsRes.status === "fulfilled") setTrends(trendsRes.value.data);
      if (healthRes.status === "fulfilled") setHealth(healthRes.value.data);
    } catch {
      setError("데이터를 불러오는 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">대시보드</h1>
          <p className="text-sm text-muted-foreground">
            AI 뉴스룸 종합 현황
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
          새로고침
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {/* Status cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card size="sm">
          <CardContent className="flex items-center gap-3">
            <div className="rounded-lg bg-blue-100 p-2">
              <Newspaper className="size-4 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">최신 기사</p>
              <p className="text-lg font-semibold">{articles.length > 0 ? articles.length + "+" : "—"}</p>
            </div>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardContent className="flex items-center gap-3">
            <div className="rounded-lg bg-amber-100 p-2">
              <TrendingUp className="size-4 text-amber-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">주요 의제</p>
              <p className="text-lg font-semibold">{agenda?.top_issues?.length ?? "—"}</p>
            </div>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardContent className="flex items-center gap-3">
            <div className="rounded-lg bg-purple-100 p-2">
              <TrendingUp className="size-4 text-purple-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">트렌드 키워드</p>
              <p className="text-lg font-semibold">{trends?.data_points?.length ?? "—"}</p>
            </div>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardContent className="flex items-center gap-3">
            <div className={`rounded-lg p-2 ${health?.database === "connected" ? "bg-emerald-100" : "bg-red-100"}`}>
              <Clock className={`size-4 ${health?.database === "connected" ? "text-emerald-600" : "text-red-600"}`} />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">시스템 상태</p>
              <p className="text-lg font-semibold">{health ? "정상" : "—"}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Latest news */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">최신 뉴스</h2>
            <Link href="/news" className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1">
              전체보기 <ArrowRight className="size-3" />
            </Link>
          </div>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-xl" />
              ))}
            </div>
          ) : articles.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                수집된 뉴스가 없습니다.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {articles.map((article) => (
                <Link key={article.id} href={`/news/${article.id}`}>
                  <Card size="sm" className="transition-colors hover:bg-muted/50">
                    <CardContent>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium leading-snug line-clamp-1">{article.title}</p>
                          <p className="mt-1 text-xs text-muted-foreground line-clamp-1">
                            {article.description}
                          </p>
                          <div className="mt-2 flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">{article.source_name}</span>
                            <span className="text-xs text-muted-foreground">
                              {new Date(article.published_at).toLocaleDateString("ko-KR")}
                            </span>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1 shrink-0">
                          {article.analysis?.category && (
                            <Badge variant="secondary" className="text-[10px]">
                              {categoryLabel[article.analysis.category] || article.analysis.category}
                            </Badge>
                          )}
                          {article.analysis?.sentiment && (
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${sentimentColor[article.analysis.sentiment]}`}>
                              {article.analysis.sentiment === "positive" ? "긍정" : article.analysis.sentiment === "negative" ? "부정" : "중립"}
                            </span>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Agenda sidebar */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">오늘의 의제</h2>
            <Link href="/analysis" className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1">
              상세 <ArrowRight className="size-3" />
            </Link>
          </div>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-xl" />
              ))}
            </div>
          ) : !agenda?.top_issues?.length ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                의제 분석 데이터가 없습니다.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {agenda.top_issues.map((issue) => (
                <Card key={issue.rank} size="sm">
                  <CardContent>
                    <div className="flex items-start gap-3">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                        {issue.rank}
                      </span>
                      <div className="min-w-0">
                        <p className="font-medium text-sm leading-snug line-clamp-1">{issue.topic}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">{issue.summary}</p>
                        <div className="mt-1.5 flex items-center gap-2">
                          <span className="text-[10px] text-muted-foreground">
                            기사 {issue.article_count}건
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            중요도 {issue.importance_score.toFixed(1)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
