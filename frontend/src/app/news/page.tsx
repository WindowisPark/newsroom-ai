"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Download,
  AlertCircle,
  AlertTriangle,
} from "lucide-react";
import { getNews, collectNews, getDashboardStats } from "@/lib/api";
import type { Article, Meta } from "@/lib/types";
import { CATEGORY_LABEL } from "@/lib/labels";
import { relativeTime } from "@/lib/time";
import { DraftDialog } from "@/components/draft-dialog";

const categories = [
  { value: "", label: "전체 카테고리" },
  { value: "politics", label: "정치" },
  { value: "economy", label: "경제" },
  { value: "society", label: "사회" },
  { value: "world", label: "국제" },
  { value: "tech", label: "기술" },
  { value: "culture", label: "문화" },
  { value: "sports", label: "스포츠" },
];

const sortOptions = [
  { value: "importance", label: "중요도순" },
  { value: "published_at", label: "최신순" },
  { value: "created_at", label: "수집순" },
];

interface Stats {
  total_articles_today: number;
  unanalyzed_count: number;
  high_importance_count: number;
}

export default function NewsPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sortBy, setSortBy] = useState("importance");

  const fetchArticles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        page: String(page),
        limit: "20",
        sort_by: sortBy,
      };
      if (query) params.q = query;
      if (category) params.category = category;
      const res = await getNews(params);
      setArticles(res.data);
      setMeta(res.meta ?? null);
    } catch {
      setError("뉴스를 불러오는 데 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }, [page, query, category, sortBy]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await getDashboardStats();
      setStats(res.data);
    } catch {
      /* 통계 실패는 무시 — 핵심 목록은 별도 경로 */
    }
  }, []);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  async function handleCollect() {
    setCollecting(true);
    try {
      const res = await collectNews();
      alert(`수집 완료: 신규 ${res.data.new_count}건 / 중복 ${res.data.duplicate_count}건`);
      fetchArticles();
      fetchStats();
    } catch {
      alert("수집 중 오류가 발생했습니다.");
    } finally {
      setCollecting(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchArticles();
  }

  const totalPages = meta ? Math.ceil(meta.total / meta.limit) : 1;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between border-b pb-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">뉴스</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {meta ? `필터 ${meta.total}건` : "수집된 뉴스 기사"}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleCollect} disabled={collecting}>
          <Download className={`size-4 ${collecting ? "animate-spin" : ""}`} />
          수동 수집
        </Button>
      </div>

      {/* 요약 스트립 — 오늘의 전체 맥락 */}
      {stats && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border bg-muted/40 px-4 py-2.5 text-sm">
          <span>
            오늘 수집 <strong className="text-foreground">{stats.total_articles_today}</strong>건
          </span>
          <span className="text-muted-foreground">·</span>
          <span>
            중요 <strong className="text-foreground">{stats.high_importance_count}</strong>건
          </span>
          {stats.unanalyzed_count > 0 && (
            <>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">
                미분석 {stats.unanalyzed_count}건
              </span>
            </>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="키워드 검색..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-8 w-56"
            />
          </div>
          <Button type="submit" size="sm" variant="secondary">검색</Button>
        </form>

        <Select value={category} onValueChange={(v) => { setCategory(v as string); setPage(1); }}>
          <SelectTrigger><SelectValue placeholder="전체 카테고리" /></SelectTrigger>
          <SelectContent>
            {categories.map((c) => (
              <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(v) => { setSortBy(v as string); setPage(1); }}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {sortOptions.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {/* Article list */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      ) : articles.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            조건에 맞는 뉴스가 없습니다.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {articles.map((article) => {
            const isHigh = (article.analysis?.importance_score ?? 0) >= 8.0;
            return (
              <Card
                key={article.id}
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
                          <AlertTriangle className="size-3.5 text-primary shrink-0" />
                        )}
                        <p className="font-medium leading-snug line-clamp-1">
                          {article.title}
                        </p>
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
                      <DraftDialog
                        articleIds={[article.id]}
                        topicHint={article.title}
                        triggerLabel="초안"
                        triggerSize="sm"
                        triggerVariant="outline"
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
