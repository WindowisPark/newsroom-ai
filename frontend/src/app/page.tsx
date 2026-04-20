"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Newspaper,
  TrendingUp,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  ArrowRight,
  Clock,
  Search,
  X,
} from "lucide-react";
import { getNews, getAgenda, getDashboardStats } from "@/lib/api";
import { useSSE } from "@/lib/use-sse";
import type { Article, AgendaData } from "@/lib/types";
import { CopyButton } from "@/components/copy-button";
import { CATEGORY_LABEL } from "@/lib/labels";

interface DashboardStats {
  total_articles_today: number;
  unanalyzed_count: number;
  high_importance_count: number;
  breaking_count: number;
  top_keywords: { keyword: string; count: number }[];
  category_distribution: Record<string, number>;
}

interface BreakingAlert {
  count: number;
  titles: string[];
  time: Date;
}

export default function DashboardPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [agenda, setAgenda] = useState<AgendaData | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [breakingAlert, setBreakingAlert] = useState<BreakingAlert | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [newsRes, agendaRes, statsRes] = await Promise.allSettled([
        getNews({ limit: "5", sort_by: "published_at" }),
        getAgenda({ top_n: "5" }),
        getDashboardStats(),
      ]);
      if (newsRes.status === "fulfilled") setArticles(newsRes.value.data);
      if (agendaRes.status === "fulfilled") setAgenda(agendaRes.value.data);
      if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
    } catch {
      setError("데이터를 불러오는 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  // SSE 이벤트로 대시보드 자동 갱신
  useSSE(
    useCallback(
      (type: string, data: Record<string, unknown>) => {
        if (["new_articles", "analysis_complete", "report_generated"].includes(type)) {
          loadData();
        }
        if (type === "breaking_alert") {
          setBreakingAlert({
            count: (data.count as number) || 0,
            titles: (data.titles as string[]) || [],
            time: new Date(),
          });
        }
      },
      [loadData]
    )
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="space-y-6">
      {/* 주요 이슈 감지 배너 — LLM 중요도 임계 기반 */}
      {breakingAlert && (
        <div className="rounded-lg border-2 border-amber-400 bg-amber-50 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="size-5 text-amber-600 shrink-0" />
            <div>
              <p className="font-semibold text-amber-900">
                주요 기사 {breakingAlert.count}건 감지
              </p>
              <p className="text-sm text-amber-700 line-clamp-1">
                {breakingAlert.titles[0]}
              </p>
            </div>
          </div>
          <Button variant="ghost" size="icon-sm" onClick={() => setBreakingAlert(null)}>
            <X className="size-4 text-amber-500" />
          </Button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">대시보드</h1>
          <p className="text-sm text-muted-foreground">AI 뉴스룸 종합 현황</p>
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

      {/* 핵심 메트릭 카드 */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card size="sm">
          <CardContent className="flex items-center gap-3">
            <div className="rounded-lg bg-blue-100 p-2">
              <Newspaper className="size-4 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">오늘 수집</p>
              <p className="text-lg font-semibold">{stats?.total_articles_today ?? "—"}건</p>
            </div>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardContent className="flex items-center gap-3">
            <div className="rounded-lg bg-amber-100 p-2">
              <AlertTriangle className="size-4 text-amber-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">중요 기사</p>
              <p className="text-lg font-semibold">
                {stats?.high_importance_count ?? "—"}건
              </p>
            </div>
          </CardContent>
        </Card>
        <Card size="sm" className={stats?.unanalyzed_count ? "ring-2 ring-amber-300" : ""}>
          <CardContent className="flex items-center gap-3">
            <div className={`rounded-lg p-2 ${stats?.unanalyzed_count ? "bg-amber-100" : "bg-emerald-100"}`}>
              <Search className={`size-4 ${stats?.unanalyzed_count ? "text-amber-600" : "text-emerald-600"}`} />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">미분석</p>
              <p className="text-lg font-semibold">
                {stats?.unanalyzed_count ?? "—"}건
              </p>
            </div>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardContent className="flex items-center gap-3">
            <div className="rounded-lg bg-emerald-100 p-2">
              <Clock className="size-4 text-emerald-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">시스템</p>
              <p className="text-lg font-semibold">정상</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 상위 키워드 */}
      {stats?.top_keywords && stats.top_keywords.length > 0 && (
        <Card size="sm">
          <CardContent>
            <p className="text-xs font-medium text-muted-foreground mb-2">오늘의 핵심 키워드</p>
            <div className="flex flex-wrap gap-1.5">
              {stats.top_keywords.map((kw) => (
                <Badge key={kw.keyword} variant="secondary" className="text-xs">
                  {kw.keyword} <span className="ml-1 text-muted-foreground">{kw.count}</span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* 최신 뉴스 */}
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
              {articles.map((article) => {
                const isHigh = (article.analysis?.importance_score ?? 0) >= 8.0;
                return (
                  <Link key={article.id} href={`/news/${article.id}`}>
                    <Card
                      size="sm"
                      className={`transition-colors hover:bg-muted/50 ${isHigh ? "border-l-4 border-l-red-500 bg-red-50/30" : ""}`}
                    >
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
                            {isHigh && (
                              <Badge variant="destructive" className="text-[10px]">중요</Badge>
                            )}
                            {article.analysis?.category && (
                              <Badge variant="secondary" className="text-[10px]">
                                {CATEGORY_LABEL[article.analysis.category] || article.analysis.category}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* 의제 사이드바 */}
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
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-sm leading-snug line-clamp-1">{issue.topic}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">{issue.summary}</p>
                        <div className="mt-1.5 flex items-center gap-2">
                          <span className="text-[10px] text-muted-foreground">
                            매체 {issue.source_count}곳
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            기사 {issue.article_count}건
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <CopyButton
                          value={`${issue.rank}. ${issue.topic}\n${issue.summary}\n(매체 ${issue.source_count}곳 · 기사 ${issue.article_count}건)`}
                          size="icon"
                          label="복사"
                        />
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
