"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Newspaper,
  FileText,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowRight,
} from "lucide-react";

import { listArticleDrafts } from "@/lib/api";
import type { ArticleDraftItem, ArticleDraftStatus } from "@/lib/types";

const categoryLabel: Record<string, string> = {
  politics: "정치", economy: "경제", society: "사회",
  world: "국제", tech: "기술", culture: "문화", sports: "스포츠",
};

const STATUS_META: Record<
  ArticleDraftStatus,
  { label: string; tabLabel: string; icon: typeof FileText; color: string }
> = {
  draft: { label: "초안", tabLabel: "내 초안", icon: FileText, color: "text-muted-foreground" },
  in_review: { label: "결재 대기", tabLabel: "결재 대기", icon: Clock, color: "text-amber-600" },
  approved: { label: "게시 완료", tabLabel: "게시 완료", icon: CheckCircle2, color: "text-emerald-600" },
  rejected: { label: "반려", tabLabel: "반려", icon: XCircle, color: "text-destructive" },
};

export default function NewsroomPage() {
  const [items, setItems] = useState<ArticleDraftItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listArticleDrafts();
      setItems(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "목록을 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const byStatus = (s: ArticleDraftStatus) => items.filter((x) => x.status === s);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Newspaper className="size-6" />
          편집실
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          예비 게시한 초안을 편집·결재·게시까지 관리합니다.
        </p>
      </header>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      <Tabs defaultValue="draft">
        <TabsList variant="line">
          <TabsTrigger value="draft">
            {STATUS_META.draft.tabLabel} ({byStatus("draft").length})
          </TabsTrigger>
          <TabsTrigger value="in_review">
            {STATUS_META.in_review.tabLabel} ({byStatus("in_review").length})
          </TabsTrigger>
          <TabsTrigger value="approved">
            {STATUS_META.approved.tabLabel} ({byStatus("approved").length})
          </TabsTrigger>
          <TabsTrigger value="rejected">
            {STATUS_META.rejected.tabLabel} ({byStatus("rejected").length})
          </TabsTrigger>
        </TabsList>
        {(["draft", "in_review", "approved", "rejected"] as ArticleDraftStatus[]).map((s) => (
          <TabsContent key={s} value={s}>
            <StatusList
              status={s}
              items={byStatus(s)}
              loading={loading}
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

function StatusList({
  status,
  items,
  loading,
}: {
  status: ArticleDraftStatus;
  items: ArticleDraftItem[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="mt-4 space-y-3">
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
    );
  }
  if (items.length === 0) {
    const msgs: Record<ArticleDraftStatus, string> = {
      draft: "작성 중인 예비 기사가 없습니다. 의제·뉴스에서 '초안 작성'을 눌러 시작하세요.",
      in_review: "결재 대기 중인 기사가 없습니다.",
      approved: "게시된 기사가 없습니다.",
      rejected: "반려된 기사가 없습니다.",
    };
    return (
      <Card className="mt-4">
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          <FileText className="mx-auto mb-2 size-8" />
          {msgs[status]}
        </CardContent>
      </Card>
    );
  }
  return (
    <div className="mt-4 space-y-3">
      {items.map((item) => (
        <ArticleDraftCard key={item.id} item={item} />
      ))}
    </div>
  );
}

function ArticleDraftCard({ item }: { item: ArticleDraftItem }) {
  const meta = STATUS_META[item.status];
  const Icon = meta.icon;
  const updated = new Date(item.updated_at).toLocaleString("ko-KR");
  return (
    <Link href={`/newsroom/${item.id}`} className="block">
      <Card className="hover:border-primary/50 transition-colors">
        <CardContent>
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1 space-y-1.5">
              <div className="flex items-center gap-2">
                <Badge
                  variant={item.status === "approved" ? "default" : "outline"}
                  className="text-[10px]"
                >
                  <Icon className={`size-3 ${meta.color}`} />
                  <span className="ml-1">{meta.label}</span>
                </Badge>
                {item.category && (
                  <Badge variant="secondary" className="text-[10px]">
                    {categoryLabel[item.category] || item.category}
                  </Badge>
                )}
              </div>
              <h3 className="font-semibold line-clamp-1">{item.title}</h3>
              <p className="text-sm text-muted-foreground line-clamp-2">
                {item.lead}
              </p>
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span>업데이트 {updated}</span>
                {item.references.length > 0 && (
                  <span>참고 {item.references.length}건</span>
                )}
                {item.review_note && (
                  <span className="italic">메모: {item.review_note.slice(0, 30)}</span>
                )}
              </div>
            </div>
            <ArrowRight className="size-4 text-muted-foreground shrink-0 mt-1" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
