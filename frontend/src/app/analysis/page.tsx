"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertCircle,
  ArrowRight,
  Search,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { CopyButton } from "@/components/copy-button";
import { DraftDialog } from "@/components/draft-dialog";
import { getAgenda, getPerspective, getTrends } from "@/lib/api";
import type { AgendaData, PerspectiveData, TrendData } from "@/lib/types";

const CHART_COLORS = [
  "hsl(221, 83%, 53%)", "hsl(262, 83%, 58%)", "hsl(339, 81%, 51%)",
  "hsl(25, 95%, 53%)", "hsl(142, 71%, 45%)", "hsl(45, 93%, 47%)",
];

const trendIcon: Record<string, typeof TrendingUp> = {
  rising: TrendingUp,
  falling: TrendingDown,
  stable: Minus,
};

export default function AnalysisPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">분석</h1>
      <Tabs defaultValue="agenda">
        <TabsList variant="line">
          <TabsTrigger value="agenda">의제 설정</TabsTrigger>
          <TabsTrigger value="perspective">관점 비교</TabsTrigger>
          <TabsTrigger value="trends">트렌드</TabsTrigger>
        </TabsList>
        <TabsContent value="agenda"><AgendaTab /></TabsContent>
        <TabsContent value="perspective"><PerspectiveTab /></TabsContent>
        <TabsContent value="trends"><TrendsTab /></TabsContent>
      </Tabs>
    </div>
  );
}

function AgendaTab() {
  const [data, setData] = useState<AgendaData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getAgenda({ top_n: "5" });
      setData(res.data);
    } catch {
      setError("의제 분석 데이터를 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return <AnalysisSkeleton />;
  if (error) return <ErrorBox message={error} />;
  if (!data) return null;

  return (
    <div className="mt-4 space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data.date} 기준 · {new Date(data.generated_at).toLocaleTimeString("ko-KR")} 생성
        </p>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="size-4" /> 새로고침
        </Button>
      </div>

      {data.analysis_summary && (
        <Card>
          <CardContent className="text-sm leading-relaxed whitespace-pre-wrap">
            {data.analysis_summary}
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {data.top_issues.map((issue) => {
          const TrendIconComp = trendIcon[issue.trend] || Minus;
          return (
            <Card key={issue.rank}>
              <CardContent>
                <div className="flex items-start gap-4">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                    {issue.rank}
                  </span>
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{issue.topic}</h3>
                      <TrendIconComp className={`size-4 ${issue.trend === "rising" ? "text-emerald-500" : issue.trend === "falling" ? "text-red-500" : "text-zinc-400"}`} />
                    </div>
                    <p className="text-sm text-muted-foreground">{issue.summary}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {issue.categories.map((cat) => (
                        <Badge key={cat} variant="secondary" className="text-[10px]">{cat}</Badge>
                      ))}
                      {issue.key_keywords.map((kw) => (
                        <Badge key={kw} variant="outline" className="text-[10px]">{kw}</Badge>
                      ))}
                    </div>
                    <div className="flex gap-4 text-xs text-muted-foreground">
                      <span>기사 {issue.article_count}건</span>
                      <span>매체 {issue.source_count}곳</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <CopyButton
                        value={`${issue.rank}. ${issue.topic}\n${issue.summary}\n(매체 ${issue.source_count}곳 · 기사 ${issue.article_count}건)`}
                        size="sm"
                        label="복사"
                        variant="ghost"
                      />
                      {issue.related_article_ids.length > 0 && (
                        <DraftDialog
                          articleIds={issue.related_article_ids}
                          topicHint={issue.topic}
                          triggerLabel="이 이슈로 초안 작성"
                          triggerVariant="outline"
                        />
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function PerspectiveTab() {
  const [topic, setTopic] = useState("");
  const [data, setData] = useState<PerspectiveData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getPerspective(topic);
      setData(res.data);
    } catch {
      setError("관점 비교 분석에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-4 space-y-6">
      <form onSubmit={handleSearch} className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="비교할 이슈 주제 입력..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="pl-8"
          />
        </div>
        <Button type="submit" disabled={loading || !topic.trim()}>
          {loading ? <RefreshCw className="size-4 animate-spin" /> : "분석"}
        </Button>
      </form>

      {error && <ErrorBox message={error} />}

      {loading && <AnalysisSkeleton />}

      {data && !loading && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">&quot;{data.topic}&quot; 관점 비교</h2>

          <div className="grid gap-4 md:grid-cols-2">
            <PerspectiveCard title="국내 매체" side={data.domestic} />
            <PerspectiveCard title="해외 매체" side={data.foreign} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>비교 분석</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">프레임 차이</p>
                <p className="text-sm">{data.comparison.frame_difference}</p>
              </div>
              <Separator />
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">배경 맥락</p>
                <p className="text-sm">{data.comparison.background_context}</p>
              </div>
              <Separator />
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">편집 시사점</p>
                <p className="text-sm">{data.comparison.editorial_insight}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

const TONE_LABEL: Record<string, string> = {
  supportive: "우호적",
  critical: "비판적",
  neutral: "중립적",
  cautious: "신중",
  // 혹시 모를 변이 — 과거 prompt 에서 허용된 값
  positive: "긍정",
  negative: "부정",
};

const TONE_COLOR: Record<string, string> = {
  supportive: "text-blue-600",
  critical: "text-amber-600",
  neutral: "text-zinc-500",
  cautious: "text-violet-600",
  positive: "text-emerald-600",
  negative: "text-red-600",
};

function PerspectiveCard({ title, side }: { title: string; side: PerspectiveData["domestic"] }) {
  const label = TONE_LABEL[side.tone] ?? side.tone;
  const colorClass = TONE_COLOR[side.tone] ?? "text-muted-foreground";

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription className={colorClass}>
          논조: {label}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm">{side.frame}</p>
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">핵심 포인트</p>
          <ul className="space-y-1">
            {side.key_points.map((point, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <ArrowRight className="size-3 mt-1 shrink-0 text-muted-foreground" />
                {point}
              </li>
            ))}
          </ul>
        </div>
        {side.representative_articles.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">대표 기사</p>
            <div className="space-y-1">
              {side.representative_articles.map((a) => (
                <a
                  key={a.id}
                  href={a.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-sm text-primary hover:underline truncate"
                >
                  [{a.source_name}] {a.title}
                </a>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TrendsTab() {
  const [data, setData] = useState<TrendData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState("24h");
  const [type, setType] = useState("keyword");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getTrends({ period, type });
      setData(res.data);
    } catch {
      setError("트렌드 데이터를 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [period, type]);

  // Transform data for recharts
  const chartData = data?.data_points?.[0]?.values.map((_, i) => {
    const point: Record<string, string | number> = {
      time: new Date(data.data_points[0].values[i].time).toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };
    data.data_points.forEach((series) => {
      point[series.label] = series.values[i]?.count ?? 0;
    });
    return point;
  }) ?? [];

  return (
    <div className="mt-4 space-y-6">
      <div className="flex items-center gap-3">
        <Select value={period} onValueChange={(v) => setPeriod(v as string)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="6h">6시간</SelectItem>
            <SelectItem value="12h">12시간</SelectItem>
            <SelectItem value="24h">24시간</SelectItem>
            <SelectItem value="7d">7일</SelectItem>
          </SelectContent>
        </Select>
        <Select value={type} onValueChange={(v) => setType(v as string)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="keyword">키워드</SelectItem>
            <SelectItem value="category">카테고리</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {error && <ErrorBox message={error} />}

      {loading ? (
        <Skeleton className="h-80 w-full rounded-xl" />
      ) : chartData.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            트렌드 데이터가 없습니다.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="pt-4">
            <ResponsiveContainer width="100%" height={360}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="time" tick={{ fontSize: 12 }} className="text-muted-foreground" />
                <YAxis tick={{ fontSize: 12 }} className="text-muted-foreground" />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid var(--border)",
                    background: "var(--popover)",
                    color: "var(--popover-foreground)",
                    fontSize: "12px",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                {data?.data_points.map((series, i) => (
                  <Line
                    key={series.label}
                    type="monotone"
                    dataKey={series.label}
                    stroke={CHART_COLORS[i % CHART_COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function AnalysisSkeleton() {
  return (
    <div className="mt-4 space-y-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <Skeleton key={i} className="h-32 w-full rounded-xl" />
      ))}
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
      <AlertCircle className="size-4" />
      {message}
    </div>
  );
}
