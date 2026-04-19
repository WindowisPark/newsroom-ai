"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  RefreshCw,
  FileText,
  Clock,
  Cpu,
  AlertCircle,
  Sparkles,
  Mail,
} from "lucide-react";
import { getBriefing, generateBriefing } from "@/lib/api";
import type { BriefingData } from "@/lib/types";
import { CopyButton } from "@/components/copy-button";

const categoryLabel: Record<string, string> = {
  politics: "정치", economy: "경제", society: "사회",
  world: "국제", tech: "기술", culture: "문화", sports: "스포츠",
};

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

function buildMailtoUrl(data: BriefingData): string {
  const { briefing } = data;
  const subject = `[뉴스 브리핑] ${briefing.headline}`;
  const bodyLines = [
    briefing.headline,
    "",
    briefing.summary,
    "",
    "[섹션]",
    ...briefing.sections.map((s) => `- ${s.title} (${categoryLabel[s.category] || s.category})`),
    "",
    "상세는 사내 대시보드에서 확인하세요.",
  ];
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(bodyLines.join("\n"))}`;
}

export default function ReportsPage() {
  const [data, setData] = useState<BriefingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getBriefing();
      setData(res.data);
    } catch {
      setError("브리핑 데이터를 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const res = await generateBriefing();
      setData(res.data);
    } catch {
      setError("브리핑 생성에 실패했습니다.");
    } finally {
      setGenerating(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">브리핑 리포트</h1>
          <p className="text-sm text-muted-foreground">AI 생성 뉴스 브리핑</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            새로고침
          </Button>
          <Button size="sm" onClick={handleGenerate} disabled={generating}>
            <Sparkles className={`size-4 ${generating ? "animate-spin" : ""}`} />
            새 브리핑 생성
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-2/3" />
          <Skeleton className="h-48 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      ) : !data ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="mx-auto mb-3 size-10 text-muted-foreground" />
            <p className="text-muted-foreground">오늘의 브리핑이 아직 생성되지 않았습니다.</p>
            <Button className="mt-4" onClick={handleGenerate} disabled={generating}>
              <Sparkles className="size-4" />
              지금 생성하기
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="mx-auto max-w-3xl space-y-6">
          {/* Meta info */}
          <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="size-3" />
              {data.date} · {new Date(data.generated_at).toLocaleTimeString("ko-KR")}
            </span>
            <span className="flex items-center gap-1">
              <Cpu className="size-3" />
              {data.model_used}
            </span>
            <span>토큰: {data.prompt_tokens + data.completion_tokens}</span>
          </div>

          {/* Export actions */}
          <div className="flex flex-wrap gap-2">
            <CopyButton
              value={buildBriefingMarkdown(data)}
              label="마크다운 전체 복사"
              variant="outline"
            />
            <a
              href={buildMailtoUrl(data)}
              className="inline-flex h-7 items-center gap-1 rounded-[min(var(--radius-md),12px)] border border-border bg-background px-2.5 text-[0.8rem] font-medium hover:bg-muted transition-colors"
            >
              <Mail className="size-3.5" />
              메일로 보내기
            </a>
          </div>

          {/* Headline */}
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">{data.briefing.headline}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {data.briefing.summary}
              </p>
            </CardContent>
          </Card>

          {/* Sections */}
          {data.briefing.sections.map((section, i) => (
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
      )}
    </div>
  );
}
