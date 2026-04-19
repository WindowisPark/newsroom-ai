"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  PenTool,
  Clock,
  RefreshCw,
  AlertCircle,
  Lightbulb,
  CalendarDays,
} from "lucide-react";
import { recommendHeadlines, getTimeline, getNews } from "@/lib/api";
import type { HeadlineData, TimelineData } from "@/lib/types";
import { CopyButton } from "@/components/copy-button";
import { DraftDialog } from "@/components/draft-dialog";

export default function HeadlinesPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">기사 작성 보조</h1>
      <p className="text-sm text-muted-foreground">AI 기반 헤드라인 추천 및 배경 타임라인 생성</p>
      <Tabs defaultValue="headlines">
        <TabsList variant="line">
          <TabsTrigger value="headlines">헤드라인 추천</TabsTrigger>
          <TabsTrigger value="timeline">배경 타임라인</TabsTrigger>
        </TabsList>
        <TabsContent value="headlines"><HeadlinesTab /></TabsContent>
        <TabsContent value="timeline"><TimelineTab /></TabsContent>
      </Tabs>
    </div>
  );
}

function HeadlinesTab() {
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState("neutral");
  const [data, setData] = useState<HeadlineData | null>(null);
  const [relatedArticleIds, setRelatedArticleIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      // 헤드라인 추천 + 관련 기사 ID 병렬 조회 (초안 작성 연결용)
      const [headlineRes, newsRes] = await Promise.all([
        recommendHeadlines(topic, [], style),
        getNews({ q: topic, limit: "5" }),
      ]);
      setData(headlineRes.data);
      setRelatedArticleIds(newsRes.data.map((a) => a.id));
    } catch {
      setError("헤드라인 추천에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  const toneLabel: Record<string, string> = {
    informative: "정보 전달", analytical: "분석적",
    engaging: "흥미 유발", neutral: "중립",
  };

  return (
    <div className="mt-4 space-y-6">
      <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="이슈 주제 또는 키워드 입력..."
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="max-w-md"
        />
        <Select value={style} onValueChange={(v) => setStyle(v as string)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="neutral">중립</SelectItem>
            <SelectItem value="informative">정보 전달</SelectItem>
            <SelectItem value="engaging">흥미 유발</SelectItem>
            <SelectItem value="analytical">분석적</SelectItem>
          </SelectContent>
        </Select>
        <Button type="submit" disabled={loading || !topic.trim()}>
          {loading ? <RefreshCw className="size-4 animate-spin" /> : <PenTool className="size-4" />}
          추천 받기
        </Button>
      </form>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {data && !loading && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            &quot;{data.topic}&quot; 관련 헤드라인 추천
          </p>
          {data.headlines.map((item, i) => (
            <Card key={i}>
              <CardContent>
                <div className="flex items-start gap-4">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-amber-100 text-sm font-bold text-amber-700">
                    {i + 1}
                  </span>
                  <div className="flex-1 space-y-2">
                    <p className="text-base font-semibold">{item.headline}</p>
                    <p className="text-sm text-muted-foreground">{item.reason}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="text-xs">
                        {toneLabel[item.tone] || item.tone}
                      </Badge>
                      <CopyButton value={item.headline} size="icon" label="제목 복사" />
                      {relatedArticleIds.length > 0 && (
                        <DraftDialog
                          articleIds={relatedArticleIds}
                          topicHint={item.headline}
                          triggerLabel="이 제목으로 초안"
                          triggerVariant="outline"
                        />
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function TimelineTab() {
  const [topic, setTopic] = useState("");
  const [data, setData] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getTimeline(topic, []);
      setData(res.data);
    } catch {
      setError("타임라인 생성에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-4 space-y-6">
      <form onSubmit={handleSubmit} className="flex items-center gap-3">
        <Input
          placeholder="이슈 주제 입력..."
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="max-w-md"
        />
        <Button type="submit" disabled={loading || !topic.trim()}>
          {loading ? <RefreshCw className="size-4 animate-spin" /> : <CalendarDays className="size-4" />}
          타임라인 생성
        </Button>
      </form>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {data && !loading && (
        <div className="mx-auto max-w-2xl space-y-6">
          <h2 className="text-lg font-semibold">&quot;{data.topic}&quot; 배경 타임라인</h2>

          {/* Timeline visualization */}
          <div className="relative pl-6">
            <div className="absolute left-2.5 top-2 bottom-2 w-px bg-border" />
            {data.timeline.map((event, i) => (
              <div key={i} className="relative mb-6 last:mb-0">
                <div className="absolute -left-3.5 top-1.5 size-2 rounded-full bg-primary ring-2 ring-background" />
                <div className="ml-4">
                  <p className="text-xs font-medium text-muted-foreground">{event.date}</p>
                  <p className="mt-0.5 font-medium text-sm">{event.event}</p>
                  <p className="mt-0.5 text-sm text-muted-foreground">{event.significance}</p>
                </div>
              </div>
            ))}
          </div>

          {data.context_summary && (
            <>
              <Separator />
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Lightbulb className="size-4" /> 맥락 요약
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {data.context_summary}
                  </p>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      )}
    </div>
  );
}
