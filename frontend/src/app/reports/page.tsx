"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  RefreshCw,
  FileText,
  Clock,
  Cpu,
  AlertCircle,
  Sparkles,
  Mail,
  AlertTriangle,
  Bookmark,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight,
} from "lucide-react";
import {
  getBriefing,
  generateBriefing,
  getAgenda,
  getNews,
  getWatchlist,
} from "@/lib/api";
import type {
  BriefingData,
  AgendaData,
  AgendaIssue,
  Article,
  WatchlistItem,
} from "@/lib/types";
import { CopyButton } from "@/components/copy-button";
import { DraftDialog } from "@/components/draft-dialog";
import { useSSE } from "@/lib/use-sse";

const categoryLabel: Record<string, string> = {
  politics: "정치", economy: "경제", society: "사회",
  world: "국제", tech: "기술", culture: "문화", sports: "스포츠",
};

const trendIcon: Record<string, typeof TrendingUp> = {
  rising: TrendingUp,
  falling: TrendingDown,
  stable: Minus,
};

const BREAKING_THRESHOLD = 8.5;

function buildBriefingMarkdown(data: BriefingData): string {
  const { briefing } = data;
  const parts: string[] = [];
  parts.push(`# ${briefing.headline}`);
  parts.push("");
  parts.push(`> 생성: ${data.generated_at} · 모델: ${data.model_used}`);
  parts.push("");
  parts.push(briefing.summary);
  for (const section of briefing.sections) {
    parts.push("");
    parts.push(`## ${section.title} (${categoryLabel[section.category] || section.category})`);
    parts.push(section.content);
  }
  return parts.join("\n");
}

function buildMailtoUrl(data: BriefingData, agenda: AgendaData | null): string {
  const { briefing } = data;
  const subject = `[뉴스룸 일일 보고] ${briefing.headline}`;
  const bodyLines = [
    briefing.headline,
    "",
    briefing.summary,
    "",
  ];
  if (agenda && agenda.top_issues.length > 0) {
    bodyLines.push("[오늘의 주요 의제]");
    for (const issue of agenda.top_issues.slice(0, 5)) {
      bodyLines.push(`- ${issue.rank}. ${issue.topic} (매체 ${issue.source_count}곳)`);
    }
    bodyLines.push("");
  }
  bodyLines.push("[분야별 브리핑]");
  for (const s of briefing.sections) {
    bodyLines.push(`- ${s.title} (${categoryLabel[s.category] || s.category})`);
  }
  bodyLines.push("");
  bodyLines.push("상세는 사내 대시보드에서 확인하세요.");
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(bodyLines.join("\n"))}`;
}

type WatchMatch = { keyword: string; articles: Article[] };

export default function ReportsPage() {
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [agenda, setAgenda] = useState<AgendaData | null>(null);
  const [breaking, setBreaking] = useState<Article[]>([]);
  const [watchMatches, setWatchMatches] = useState<WatchMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [briefingRes, agendaRes, newsRes, watchRes] = await Promise.all([
        getBriefing().catch(() => null),
        getAgenda({ top_n: "5" }).catch(() => null),
        getNews({ sort_by: "importance", limit: "20" }).catch(() => null),
        getWatchlist().catch(() => null),
      ]);

      setBriefing(briefingRes?.data ?? null);
      setAgenda(agendaRes?.data ?? null);

      // 속보: 중요도 임계 이상. 오늘 수집건 우선
      const highImpact = (newsRes?.data ?? [])
        .filter((a) => a.analysis && a.analysis.importance_score >= BREAKING_THRESHOLD)
        .slice(0, 6);
      setBreaking(highImpact);

      // 워치리스트 매칭: 활성 키워드 최대 5개에 대해 최근 기사 3건씩 조회
      const active = (watchRes?.data ?? []).filter((w) => w.is_active).slice(0, 5);
      const matches = await Promise.all(
        active.map(async (w: WatchlistItem) => {
          const r = await getNews({ q: w.keyword, limit: "3", sort_by: "collected_at" }).catch(() => null);
          return { keyword: w.keyword, articles: r?.data ?? [] } as WatchMatch;
        })
      );
      setWatchMatches(matches.filter((m) => m.articles.length > 0));
    } catch {
      setError("보고 데이터를 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const res = await generateBriefing();
      setBriefing(res.data);
      await load();
    } catch {
      setError("브리핑 생성에 실패했습니다.");
    } finally {
      setGenerating(false);
    }
  }

  useEffect(() => {
    void load();
  }, [load]);

  // 새 기사·분석·리포트·워치 매칭 이벤트 발생 시 자동 갱신
  useSSE((type) => {
    if (
      type === "report_generated" ||
      type === "analysis_complete" ||
      type === "watchlist_match" ||
      type === "breaking_alert"
    ) {
      void load();
    }
  });

  if (loading && !briefing) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-2/3" />
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Header */}
      <header className="space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">📰 오늘의 뉴스룸 보고</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              AI 자동 수집·분석 결과를 한 장으로 확인합니다.
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
              새로고침
            </Button>
            <Button size="sm" onClick={handleGenerate} disabled={generating}>
              <Sparkles className={`size-4 ${generating ? "animate-spin" : ""}`} />
              새 브리핑 생성
            </Button>
          </div>
        </div>

        {briefing && (
          <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="size-3" />
              {briefing.date} · {new Date(briefing.generated_at).toLocaleTimeString("ko-KR")}
            </span>
            <span className="flex items-center gap-1">
              <Cpu className="size-3" />
              {briefing.model_used}
            </span>
            <span>토큰 {briefing.prompt_tokens + briefing.completion_tokens}</span>
          </div>
        )}

        {briefing && (
          <div className="flex flex-wrap gap-2 pt-1">
            <CopyButton
              value={buildBriefingMarkdown(briefing)}
              label="마크다운 전체 복사"
              variant="outline"
            />
            <a
              href={buildMailtoUrl(briefing, agenda)}
              className="inline-flex h-7 items-center gap-1 rounded-[min(var(--radius-md),12px)] border border-border bg-background px-2.5 text-[0.8rem] font-medium hover:bg-muted transition-colors"
            >
              <Mail className="size-3.5" />
              메일로 보내기
            </a>
          </div>
        )}
      </header>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {/* ① 헤드라인 & 종합 요약 */}
      {briefing ? (
        <section aria-labelledby="sec-briefing">
          <SectionHeader id="sec-briefing" num="①" title="헤드라인 & 종합 요약" />
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">{briefing.briefing.headline}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {briefing.briefing.summary}
              </p>
            </CardContent>
          </Card>
        </section>
      ) : (
        <section>
          <SectionHeader num="①" title="헤드라인 & 종합 요약" />
          <Card>
            <CardContent className="py-8 text-center">
              <FileText className="mx-auto mb-3 size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                오늘의 브리핑이 아직 생성되지 않았습니다.
              </p>
              <Button
                className="mt-3"
                size="sm"
                onClick={handleGenerate}
                disabled={generating}
              >
                <Sparkles className="size-4" />
                지금 생성
              </Button>
            </CardContent>
          </Card>
        </section>
      )}

      {/* ② 오늘의 주요 의제 Top 5 */}
      {agenda && agenda.top_issues.length > 0 && (
        <section aria-labelledby="sec-agenda">
          <SectionHeader
            id="sec-agenda"
            num="②"
            title="오늘의 주요 의제 Top 5"
            meta={`${agenda.date} 기준`}
          />
          <div className="space-y-2">
            {agenda.top_issues.map((issue) => (
              <AgendaCard key={issue.rank} issue={issue} />
            ))}
          </div>
        </section>
      )}

      {/* ③ 속보 */}
      {breaking.length > 0 && (
        <section aria-labelledby="sec-breaking">
          <SectionHeader
            id="sec-breaking"
            num="③"
            title="속보 감지"
            meta={`중요도 ${BREAKING_THRESHOLD}+ · ${breaking.length}건`}
            accent="destructive"
          />
          <div className="space-y-2">
            {breaking.map((article) => (
              <BreakingCard key={article.id} article={article} />
            ))}
          </div>
        </section>
      )}

      {/* 🔖 내 워치리스트 매칭 */}
      {watchMatches.length > 0 && (
        <section aria-labelledby="sec-watch">
          <SectionHeader
            id="sec-watch"
            num="🔖"
            title="내 워치리스트 매칭"
            meta={`${watchMatches.length}개 키워드`}
          />
          <div className="space-y-3">
            {watchMatches.map((m) => (
              <WatchGroup key={m.keyword} match={m} />
            ))}
          </div>
        </section>
      )}

      {/* ④ 분야별 브리핑 */}
      {briefing && briefing.briefing.sections.length > 0 && (
        <section aria-labelledby="sec-sections">
          <SectionHeader id="sec-sections" num="④" title="분야별 브리핑" />
          <div className="space-y-3">
            {briefing.briefing.sections.map((section, i) => (
              <Card key={i}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">
                        {categoryLabel[section.category] || section.category}
                      </Badge>
                      <CardTitle className="text-base">{section.title}</CardTitle>
                    </div>
                    <CopyButton
                      value={`## ${section.title}\n${section.content}`}
                      size="icon"
                      label="섹션 복사"
                    />
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {section.content}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ───────── Section helpers ─────────

function SectionHeader({
  id,
  num,
  title,
  meta,
  accent,
}: {
  id?: string;
  num: string;
  title: string;
  meta?: string;
  accent?: "destructive";
}) {
  return (
    <div className="mb-3 flex items-baseline justify-between">
      <h2
        id={id}
        className={`flex items-baseline gap-2 text-base font-semibold ${
          accent === "destructive" ? "text-destructive" : ""
        }`}
      >
        <span className="text-muted-foreground">{num}</span>
        {title}
      </h2>
      {meta && <span className="text-xs text-muted-foreground">{meta}</span>}
    </div>
  );
}

function AgendaCard({ issue }: { issue: AgendaIssue }) {
  const TrendIconComp = trendIcon[issue.trend] || Minus;
  const copyValue = `${issue.rank}. ${issue.topic}\n${issue.summary}\n(매체 ${issue.source_count}곳 · 기사 ${issue.article_count}건)`;
  return (
    <Card>
      <CardContent>
        <div className="flex items-start gap-3">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
            {issue.rank}
          </span>
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold">{issue.topic}</h3>
              <TrendIconComp
                className={`size-4 ${
                  issue.trend === "rising"
                    ? "text-emerald-500"
                    : issue.trend === "falling"
                    ? "text-red-500"
                    : "text-zinc-400"
                }`}
              />
            </div>
            <p className="text-sm text-muted-foreground">{issue.summary}</p>
            <div className="flex flex-wrap gap-1.5">
              {issue.key_keywords.slice(0, 3).map((kw) => (
                <Badge key={kw} variant="outline" className="text-[10px]">
                  {kw}
                </Badge>
              ))}
            </div>
            <div className="flex gap-3 text-xs text-muted-foreground">
              <span>매체 {issue.source_count}곳</span>
              <span>기사 {issue.article_count}건</span>
              <span>중요도 {issue.importance_score.toFixed(1)}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <CopyButton value={copyValue} size="sm" label="복사" variant="ghost" />
              {issue.related_article_ids.length > 0 && (
                <DraftDialog
                  articleIds={issue.related_article_ids}
                  topicHint={issue.topic}
                  triggerLabel="이 이슈로 초안"
                  triggerVariant="outline"
                />
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function BreakingCard({ article }: { article: Article }) {
  const pub = new Date(article.published_at || article.collected_at).toLocaleTimeString("ko-KR");
  const score = article.analysis?.importance_score ?? 0;
  return (
    <Card className="border-destructive/40">
      <CardContent>
        <div className="flex items-start gap-3">
          <AlertTriangle className="size-5 shrink-0 text-destructive mt-0.5" />
          <div className="flex-1 min-w-0 space-y-1.5">
            <Link
              href={`/news/${article.id}`}
              className="font-semibold hover:underline line-clamp-2"
            >
              {article.title}
            </Link>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{article.source_name}</span>
              <span>·</span>
              <span>{pub}</span>
              <span>·</span>
              <Badge variant="destructive" className="text-[10px]">
                중요도 {score.toFixed(1)}
              </Badge>
            </div>
            {article.description && (
              <p className="text-sm text-muted-foreground line-clamp-2">
                {article.description}
              </p>
            )}
            <div className="flex items-center gap-2 pt-1">
              <CopyButton
                value={`${article.title}\n${article.source_name} · ${pub}\n${article.url}`}
                size="sm"
                label="복사"
                variant="ghost"
              />
              <DraftDialog
                articleIds={[article.id]}
                topicHint={article.title}
                triggerLabel="초안"
                triggerVariant="outline"
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function WatchGroup({ match }: { match: WatchMatch }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Bookmark className="size-4 text-primary" />
          <CardTitle className="text-base">{match.keyword}</CardTitle>
          <Badge variant="secondary" className="text-[10px]">
            {match.articles.length}건
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {match.articles.map((a) => (
            <li key={a.id} className="flex items-center gap-2">
              <ArrowRight className="size-3 text-muted-foreground shrink-0" />
              <Link
                href={`/news/${a.id}`}
                className="flex-1 text-sm hover:underline line-clamp-1"
              >
                {a.title}
              </Link>
              <span className="text-xs text-muted-foreground shrink-0">
                {a.source_name}
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex items-center gap-2">
          <DraftDialog
            articleIds={match.articles.map((a) => a.id)}
            topicHint={match.keyword}
            triggerLabel={`"${match.keyword}" 초안`}
            triggerVariant="outline"
            triggerSize="sm"
          />
        </div>
      </CardContent>
    </Card>
  );
}
