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
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Download,
  AlertCircle,
} from "lucide-react";
import { getNews, collectNews } from "@/lib/api";
import type { Article, Meta } from "@/lib/types";

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

const sentiments = [
  { value: "", label: "전체 감성" },
  { value: "positive", label: "긍정" },
  { value: "negative", label: "부정" },
  { value: "neutral", label: "중립" },
];

const sortOptions = [
  { value: "importance", label: "중요도순" },
  { value: "published_at", label: "최신순" },
  { value: "created_at", label: "수집순" },
];

const categoryLabel: Record<string, string> = {
  politics: "정치", economy: "경제", society: "사회",
  world: "국제", tech: "기술", culture: "문화", sports: "스포츠",
};

const sentimentStyle: Record<string, string> = {
  positive: "bg-emerald-100 text-emerald-700",
  negative: "bg-red-100 text-red-700",
  neutral: "bg-zinc-100 text-zinc-700",
};

export default function NewsPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sentiment, setSentiment] = useState("");
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
      if (sentiment) params.sentiment = sentiment;
      const res = await getNews(params);
      setArticles(res.data);
      setMeta(res.meta ?? null);
    } catch {
      setError("뉴스를 불러오는 데 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }, [page, query, category, sentiment, sortBy]);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  async function handleCollect() {
    setCollecting(true);
    try {
      const res = await collectNews();
      alert(`수집 완료: 신규 ${res.data.new_count}건 / 중복 ${res.data.duplicate_count}건`);
      fetchArticles();
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">뉴스</h1>
          <p className="text-sm text-muted-foreground">
            {meta ? `총 ${meta.total}건` : "수집된 뉴스 기사"}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleCollect} disabled={collecting}>
          <Download className={`size-4 ${collecting ? "animate-spin" : ""}`} />
          수동 수집
        </Button>
      </div>

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

        <Select value={sentiment} onValueChange={(v) => { setSentiment(v as string); setPage(1); }}>
          <SelectTrigger><SelectValue placeholder="전체 감성" /></SelectTrigger>
          <SelectContent>
            {sentiments.map((s) => (
              <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
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
            <Link key={article.id} href={`/news/${article.id}`}>
              <Card size="sm" className={`transition-colors hover:bg-muted/50 ${isHigh ? "border-l-4 border-l-red-500 bg-red-50/30" : ""}`}>
                <CardContent>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium leading-snug line-clamp-1">{article.title}</p>
                      <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                        {article.description}
                      </p>
                      <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{article.source_name}</span>
                        <span>{article.source_type === "domestic" ? "국내" : "해외"}</span>
                        <span>{new Date(article.published_at).toLocaleString("ko-KR")}</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      {isHigh && (
                        <Badge variant="destructive" className="text-[10px]">중요</Badge>
                      )}
                      {article.analysis?.category && (
                        <Badge variant="secondary" className="text-[10px]">
                          {categoryLabel[article.analysis.category] || article.analysis.category}
                        </Badge>
                      )}
                      {article.analysis?.sentiment && (
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${sentimentStyle[article.analysis.sentiment]}`}>
                          {article.analysis.sentiment === "positive" ? "긍정" : article.analysis.sentiment === "negative" ? "부정" : "중립"}
                        </span>
                      )}
                      {article.analysis?.importance_score != null && (
                        <span className="text-[10px] text-muted-foreground">
                          중요도 {article.analysis.importance_score.toFixed(1)}
                        </span>
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
