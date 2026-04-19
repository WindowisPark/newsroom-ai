"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Bookmark, Plus, Power, Trash2, AlertCircle } from "lucide-react";

import {
  getWatchlist,
  addWatchlist,
  patchWatchlist,
  deleteWatchlist,
} from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";
import { useSSE } from "@/lib/use-sse";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getWatchlist();
      setItems(res.data);
    } catch {
      setError("워치리스트를 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // 매칭 이벤트 수신 시 목록 재조회 (match_count / last_matched_at 갱신)
  useSSE((type) => {
    if (type === "watchlist_match") {
      void load();
    }
  });

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = keyword.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setError(null);
    try {
      await addWatchlist(trimmed);
      setKeyword("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "추가 실패");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (item: WatchlistItem) => {
    try {
      await patchWatchlist(item.id, !item.is_active);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "상태 변경 실패");
    }
  };

  const handleDelete = async (item: WatchlistItem) => {
    if (!confirm(`"${item.keyword}" 를 삭제할까요?`)) return;
    try {
      await deleteWatchlist(item.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제 실패");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bookmark className="size-6" />
          워치리스트
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          관심 키워드를 등록하면 새로 수집·분석된 기사에 키워드가 포함될 때
          실시간 알림을 받습니다.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">새 키워드 등록</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="flex items-center gap-2">
            <Input
              placeholder="예) 호르무즈, 환율, AI 규제"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              disabled={submitting}
              maxLength={100}
              className="max-w-md"
            />
            <Button type="submit" disabled={submitting || !keyword.trim()}>
              <Plus className="size-4" />
              등록
            </Button>
          </form>
          {error && (
            <div className="mt-3 flex items-center gap-2 rounded border border-destructive/50 bg-destructive/10 p-2 text-sm text-destructive">
              <AlertCircle className="size-4" />
              {error}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            등록된 키워드 ({items.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">
              아직 등록된 키워드가 없습니다.
            </p>
          ) : (
            <ul className="divide-y">
              {items.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center gap-3 py-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{item.keyword}</span>
                      {item.is_active ? (
                        <Badge variant="default" className="text-[10px]">
                          활성
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px]">
                          비활성
                        </Badge>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      매칭 {item.match_count}회
                      {item.last_matched_at && (
                        <>
                          {" "}
                          · 최근 {new Date(item.last_matched_at).toLocaleString(
                            "ko-KR"
                          )}
                        </>
                      )}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => handleToggle(item)}
                  >
                    <Power className="size-3.5" />
                    {item.is_active ? "비활성화" : "활성화"}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDelete(item)}
                  >
                    <Trash2 className="size-3.5 text-destructive" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
