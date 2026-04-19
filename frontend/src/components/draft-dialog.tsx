"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FileEdit, Loader2, BookOpen, ExternalLink, Sparkles, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { CopyButton } from "@/components/copy-button";
import { generateDraft, createArticleDraft } from "@/lib/api";
import type { DraftData, DraftStyle } from "@/lib/types";

interface DraftDialogProps {
  articleIds: string[];
  topicHint?: string;
  triggerLabel?: string;
  triggerSize?: "sm" | "default";
  triggerVariant?: "default" | "secondary" | "outline";
  disabled?: boolean;
}

const STYLE_OPTIONS: { value: DraftStyle; label: string; desc: string }[] = [
  { value: "straight", label: "스트레이트", desc: "객관 사실 전달" },
  { value: "analysis", label: "분석", desc: "배경·영향 분석 확장" },
  { value: "feature", label: "피처", desc: "인물·사례 스토리" },
];

export function DraftDialog({
  articleIds,
  topicHint,
  triggerLabel = "이 자료로 초안 작성",
  triggerSize = "sm",
  triggerVariant = "default",
  disabled,
}: DraftDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState<DraftStyle>("straight");
  const [loading, setLoading] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftData | null>(null);

  const handlePublishPreliminary = async () => {
    if (!draft) return;
    setPublishing(true);
    setError(null);
    try {
      const title = draft.title_candidates[0] ?? "제목 미확정";
      const res = await createArticleDraft({
        title,
        lead: draft.lead,
        body: draft.body,
        background: draft.background,
        style,
        topic_hint: topicHint,
        six_w_check: draft.six_w_check,
        sources: draft.sources,
        references: draft.references,
        background_sources: draft.background_sources,
        style_anchor: draft.style_anchor,
        origin_article_ids: articleIds,
        model_used: draft.model_used,
      });
      const id = res.data.id;
      setOpen(false);
      router.push(`/newsroom/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "예비 게시 실패");
    } finally {
      setPublishing(false);
    }
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setDraft(null);
    try {
      const res = await generateDraft(articleIds, style, topicHint);
      setDraft(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "초안 생성 실패");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) {
      // 닫힐 때 결과 초기화
      setDraft(null);
      setError(null);
      setStyle("straight");
    }
  };

  const fullMarkdown = draft ? buildMarkdown(draft) : "";

  return (
    <>
      <Button
        type="button"
        size={triggerSize}
        variant={triggerVariant}
        disabled={disabled || articleIds.length === 0}
        className="gap-1.5"
        onClick={() => setOpen(true)}
      >
        <FileEdit className="size-3.5" />
        {triggerLabel}
      </Button>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>AI 기사 초안</DialogTitle>
          <DialogDescription>
            관련 기사 {articleIds.length}건을 기반으로 Sonnet 4.6이 역피라미드 + 6하원칙 초안을 작성합니다.
          </DialogDescription>
        </DialogHeader>

        {!draft && (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">톤 · 스타일</label>
              <div className="grid grid-cols-3 gap-2">
                {STYLE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setStyle(opt.value)}
                    className={`rounded-lg border p-3 text-left text-xs transition ${
                      style === opt.value
                        ? "border-primary bg-primary/5"
                        : "hover:border-muted-foreground/50"
                    }`}
                  >
                    <div className="font-semibold">{opt.label}</div>
                    <div className="text-muted-foreground mt-0.5">{opt.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {topicHint && (
              <div className="text-xs text-muted-foreground">
                진입 맥락: <span className="font-medium">{topicHint}</span>
              </div>
            )}

            {error && (
              <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}
          </div>
        )}

        {draft && (
          <div className="space-y-5">
            {/* 제목 후보 3안 */}
            <section>
              <h3 className="text-sm font-semibold mb-2">제목 후보</h3>
              <div className="space-y-2">
                {draft.title_candidates.map((title, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 rounded border p-2"
                  >
                    <Badge variant="outline" className="shrink-0">
                      {i + 1}
                    </Badge>
                    <span className="flex-1 text-sm">{title}</span>
                    <CopyButton value={title} size="icon" label="복사" />
                  </div>
                ))}
              </div>
            </section>

            {/* 리드 */}
            <section>
              <h3 className="text-sm font-semibold mb-2">리드</h3>
              <p className="rounded bg-muted/50 p-3 text-sm leading-relaxed">
                {draft.lead}
              </p>
            </section>

            {/* 본문 */}
            <section>
              <h3 className="text-sm font-semibold mb-2">본문</h3>
              <div className="rounded border p-3 text-sm leading-relaxed whitespace-pre-wrap">
                {draft.body}
              </div>
            </section>

            {/* 맥락/배경 */}
            {draft.background && (
              <section>
                <h3 className="text-sm font-semibold mb-2">맥락 · 배경</h3>
                <p className="rounded bg-muted/50 p-3 text-sm leading-relaxed whitespace-pre-wrap">
                  {draft.background}
                </p>
              </section>
            )}

            {/* 6하원칙 체크 */}
            <section>
              <h3 className="text-sm font-semibold mb-2">6하원칙 자체 점검</h3>
              <SixWList check={draft.six_w_check} />
            </section>

            {/* RAG: 참고 자료 (투명 공개 — 인용 가능 + 맥락용 구분) */}
            <ReferencesPanel
              references={draft.references || []}
              anchor={draft.style_anchor || null}
              backgroundSources={draft.background_sources || []}
            />

            {/* 출처 */}
            {draft.sources.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold mb-2">출처</h3>
                <ul className="space-y-1 text-sm">
                  {draft.sources.map((s, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <Badge variant="secondary">{s.name}</Badge>
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline truncate"
                      >
                        {s.url}
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <div className="text-xs text-muted-foreground">
              모델: {draft.model_used} · 토큰 {draft.prompt_tokens}/{draft.completion_tokens}
            </div>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          {!draft && (
            <Button
              type="button"
              onClick={handleGenerate}
              disabled={loading}
              className="gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  작성 중...
                </>
              ) : (
                "초안 생성"
              )}
            </Button>
          )}
          {draft && (
            <>
              <CopyButton
                value={fullMarkdown}
                label="전체 Markdown 복사"
                variant="outline"
              />
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setDraft(null);
                  setError(null);
                }}
              >
                다시 생성
              </Button>
              <Button
                type="button"
                onClick={handlePublishPreliminary}
                disabled={publishing}
                className="gap-1.5"
              >
                {publishing ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    저장 중...
                  </>
                ) : (
                  <>
                    <Send className="size-3.5" />
                    예비 기사로 게시
                  </>
                )}
              </Button>
            </>
          )}
        </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function SixWList({ check }: { check: DraftData["six_w_check"] }) {
  const labels: [keyof DraftData["six_w_check"], string][] = [
    ["who", "누가"],
    ["when", "언제"],
    ["where", "어디서"],
    ["what", "무엇을"],
    ["how", "어떻게"],
    ["why", "왜"],
  ];
  return (
    <ul className="grid grid-cols-2 gap-2 text-sm">
      {labels.map(([key, ko]) => {
        const val = check[key];
        const missing = val == null || val === "";
        return (
          <li
            key={key}
            className={`rounded border p-2 ${
              missing ? "border-destructive/40 bg-destructive/5" : ""
            }`}
          >
            <div className="text-xs text-muted-foreground">{ko}</div>
            <div className={missing ? "text-destructive text-xs" : "font-medium"}>
              {missing ? "미확인" : val}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function ReferencesPanel({
  references,
  anchor,
  backgroundSources,
}: {
  references: DraftData["references"];
  anchor: DraftData["style_anchor"];
  backgroundSources: DraftData["background_sources"];
}) {
  const nothing =
    references.length === 0 && !anchor && backgroundSources.length === 0;
  return (
    <section className="space-y-3">
      {/* 자사·통신사 (인용 가능) */}
      <div>
        <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
          <BookOpen className="size-3.5" />
          인용 가능 참고 자료
          {references.length > 0 && (
            <Badge variant="secondary" className="text-[10px]">
              {references.length}건
            </Badge>
          )}
        </h3>
        {nothing ? (
          <p className="rounded border border-dashed p-3 text-xs text-muted-foreground">
            매칭된 참고 기사가 없어 입력 기사만으로 작성되었습니다.
          </p>
        ) : references.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            자사/통신사 인용 원천 없음
          </p>
        ) : (
          <div className="space-y-2">
            {references.map((r, i) => (
              <a
                key={i}
                href={r.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-2 rounded border p-2 text-sm hover:bg-muted transition-colors"
              >
                <Badge variant="outline" className="shrink-0 mt-0.5">
                  R{i + 1}
                </Badge>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1">
                    <span className="font-medium truncate">{r.name}</span>
                    <ExternalLink className="size-3 text-muted-foreground shrink-0" />
                  </div>
                  {r.published_at && (
                    <div className="text-[11px] text-muted-foreground mt-0.5">
                      발행 {new Date(r.published_at).toLocaleDateString("ko-KR")}
                    </div>
                  )}
                  <div className="text-[11px] text-primary truncate mt-0.5">
                    {r.url}
                  </div>
                </div>
              </a>
            ))}
          </div>
        )}
      </div>

      {/* 톤 샘플 */}
      {anchor && (
        <div className="flex items-start gap-2 rounded border border-dashed p-2 text-sm">
          <Sparkles className="size-3.5 text-amber-500 mt-0.5 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-xs text-muted-foreground">
              톤 샘플 (문체 참고 · 본문에 직접 사용하지 않음)
            </div>
            <a
              href={anchor.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary hover:underline truncate block"
            >
              {anchor.url}
            </a>
          </div>
        </div>
      )}

      {/* 경쟁 일간지 맥락 (인용 금지) */}
      {backgroundSources.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold mb-2 flex items-center gap-1.5 text-muted-foreground">
            경쟁 일간지 맥락 (직접 인용하지 않음)
            <Badge variant="outline" className="text-[10px]">
              {backgroundSources.length}건
            </Badge>
          </h3>
          <ul className="space-y-1">
            {backgroundSources.map((b, i) => (
              <li
                key={i}
                className="flex items-center gap-2 text-xs text-muted-foreground"
              >
                <Badge variant="outline" className="text-[10px] shrink-0">
                  {b.name}
                </Badge>
                <a
                  href={b.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate hover:text-primary"
                >
                  {b.url}
                </a>
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-[11px] text-muted-foreground">
            ※ 국내 언론 관행상 경쟁 일간지는 본문에 매체명으로 인용하지 않습니다.
            맥락 파악용으로만 참고.
          </p>
        </div>
      )}
    </section>
  );
}

function buildMarkdown(d: DraftData): string {
  const parts: string[] = [];
  parts.push(`# ${d.title_candidates[0] ?? "기사 초안"}`);
  if (d.title_candidates.length > 1) {
    parts.push(`> 제목 후보: ${d.title_candidates.slice(1).join(" / ")}`);
  }
  parts.push("");
  parts.push(d.lead);
  parts.push("");
  parts.push(d.body);
  if (d.background) {
    parts.push("");
    parts.push("## 맥락 · 배경");
    parts.push(d.background);
  }
  if (d.sources.length > 0) {
    parts.push("");
    parts.push("## 출처");
    parts.push(...d.sources.map((s) => `- ${s.name}: ${s.url}`));
  }
  if (d.references && d.references.length > 0) {
    parts.push("");
    parts.push("## 참고한 자사 기사 (RAG)");
    parts.push(
      ...d.references.map(
        (r) => `- ${r.name}${r.published_at ? ` (${r.published_at.slice(0, 10)})` : ""}: ${r.url}`
      )
    );
  }
  return parts.join("\n");
}
