"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  Pencil,
  Save,
  X,
  Send,
  CheckCircle2,
  XCircle,
  Trash2,
  Undo2,
  AlertCircle,
  ExternalLink,
  Sparkles,
  BookOpen,
  Clock,
  FileText,
  ShieldAlert,
  ShieldCheck,
  Bot,
} from "lucide-react";

import {
  getArticleDraft,
  updateArticleDraft,
  transitionArticleDraft,
  deleteArticleDraft,
  acknowledgeFactIssue,
} from "@/lib/api";
import type {
  ArticleDraftItem,
  ArticleDraftStatus,
  FactIssue,
  FactIssueKind,
  FactIssueSeverity,
} from "@/lib/types";
import { CopyButton } from "@/components/copy-button";
import { CATEGORY_LABEL } from "@/lib/labels";
import { STATUS_BADGE_CLASS, STATUS_LABEL } from "@/lib/draft-status";
import { buildArticleMarkdown } from "@/lib/markdown";

const SEVERITY_ORDER: Record<FactIssueSeverity, number> = { high: 0, medium: 1, low: 2 };

const KIND_LABEL: Record<FactIssueKind, string> = {
  role_mismatch: "직책 오류",
  number_unsupported: "수치 미확인",
  entity_unknown: "미등재 인물",
};

const SEV_COLOR: Record<FactIssueSeverity, string> = {
  high: "border-destructive/50 bg-destructive/5",
  medium: "border-amber-300 bg-amber-50/50",
  low: "border-muted bg-muted/20",
};

const SEV_BADGE_COLOR: Record<FactIssueSeverity, string> = {
  high: "bg-destructive/10 text-destructive",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-muted text-muted-foreground",
};

export default function NewsroomDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const [item, setItem] = useState<ArticleDraftItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftLead, setDraftLead] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [draftBackground, setDraftBackground] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getArticleDraft(id);
      setItem(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const beginEdit = () => {
    if (!item) return;
    setDraftTitle(item.title);
    setDraftLead(item.lead);
    setDraftBody(item.body);
    setDraftBackground(item.background || "");
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setError(null);
  };

  const saveEdit = async () => {
    if (!item) return;
    setSaving(true);
    setError(null);
    try {
      const res = await updateArticleDraft(item.id, {
        title: draftTitle,
        lead: draftLead,
        body: draftBody,
        background: draftBackground,
      });
      setItem(res.data);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  const transition = async (to: ArticleDraftStatus, note?: string) => {
    if (!item) return;
    setError(null);
    try {
      const res = await transitionArticleDraft(item.id, to, note);
      setItem(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "상태 변경 실패");
    }
  };

  const handleSubmitReview = () => transition("in_review");
  const handleApprove = () => transition("approved", "승인");
  const handleReject = async () => {
    const note = prompt("반려 사유를 입력하세요", "반려");
    if (note === null) return;
    await transition("rejected", note);
  };
  const handleBackToDraft = () => transition("draft", "재작성");

  const handleAckIssue = async (issue: FactIssue, acknowledged: boolean) => {
    if (!item) return;
    try {
      const note = acknowledged
        ? prompt("확인 메모 (선택)", "원문 확인 완료") ?? undefined
        : undefined;
      const res = await acknowledgeFactIssue(item.id, issue.id, {
        acknowledged,
        acknowledged_by: "편집자",
        note,
      });
      setItem(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "확인 처리 실패");
    }
  };

  const handleDelete = async () => {
    if (!item) return;
    if (!confirm(`"${item.title}" 을(를) 삭제할까요?`)) return;
    try {
      await deleteArticleDraft(item.id);
      router.push("/newsroom");
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제 실패");
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  if (error && !item) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Link href="/newsroom">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="size-4" /> 편집실
          </Button>
        </Link>
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  if (!item) return null;

  const canEdit = item.status === "draft" || item.status === "rejected";
  const canSubmit = item.status === "draft";
  const canApproveReject = item.status === "in_review";
  const canRevertToDraft = item.status === "in_review" || item.status === "approved" || item.status === "rejected";

  const highIssues = item.fact_issues.filter((i) => i.severity === "high");
  const unackHigh = highIssues.filter((i) => !i.acknowledged);
  const totalAck = item.fact_issues.filter((i) => i.acknowledged).length;
  const approveBlocked = canApproveReject && unackHigh.length > 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <Link href="/newsroom">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="size-4" /> 편집실
          </Button>
        </Link>
        <Badge className={STATUS_BADGE_CLASS[item.status]}>
          <FileText className="size-3" />
          <span className="ml-1">{STATUS_LABEL[item.status]}</span>
        </Badge>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {/* Meta */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        {item.category && (
          <Badge variant="secondary">
            {CATEGORY_LABEL[item.category] || item.category}
          </Badge>
        )}
        <span className="flex items-center gap-1">
          <Clock className="size-3" />
          업데이트 {new Date(item.updated_at).toLocaleString("ko-KR")}
        </span>
        {item.submitted_at && (
          <span>결재 요청 {new Date(item.submitted_at).toLocaleString("ko-KR")}</span>
        )}
        {item.reviewed_at && (
          <span>검토 {new Date(item.reviewed_at).toLocaleString("ko-KR")}</span>
        )}
        {item.model_used && <span>모델 {item.model_used}</span>}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        {canEdit && !editing && (
          <Button size="sm" onClick={beginEdit} className="gap-1.5">
            <Pencil className="size-3.5" />
            편집
          </Button>
        )}
        {editing && (
          <>
            <Button size="sm" onClick={saveEdit} disabled={saving} className="gap-1.5">
              <Save className="size-3.5" />
              {saving ? "저장 중..." : "저장"}
            </Button>
            <Button size="sm" variant="secondary" onClick={cancelEdit}>
              <X className="size-3.5" />
              취소
            </Button>
          </>
        )}
        {canSubmit && !editing && (
          <Button size="sm" variant="outline" onClick={handleSubmitReview} className="gap-1.5">
            <Send className="size-3.5" />
            상급자 결재 요청
          </Button>
        )}
        {canApproveReject && (
          <>
            <Button
              size="sm"
              onClick={handleApprove}
              className="gap-1.5"
              disabled={approveBlocked}
              title={
                approveBlocked
                  ? `미확인 팩트 경고 ${unackHigh.length}건을 먼저 확인하세요`
                  : undefined
              }
            >
              <CheckCircle2 className="size-3.5" />
              승인·게시
              {approveBlocked && ` (경고 ${unackHigh.length}건 미확인)`}
            </Button>
            <Button size="sm" variant="destructive" onClick={handleReject} className="gap-1.5">
              <XCircle className="size-3.5" />
              반려
            </Button>
          </>
        )}
        {canRevertToDraft && !editing && (
          <Button size="sm" variant="outline" onClick={handleBackToDraft} className="gap-1.5">
            <Undo2 className="size-3.5" />
            초안으로 복귀
          </Button>
        )}
        {!editing && (
          <Button size="sm" variant="ghost" onClick={handleDelete} className="gap-1.5 ml-auto">
            <Trash2 className="size-3.5 text-destructive" />
            삭제
          </Button>
        )}
      </div>

      {item.fact_issues.length > 0 && (
        <FactCheckCard
          issues={item.fact_issues}
          onAck={handleAckIssue}
          totalAck={totalAck}
        />
      )}

      {/* Review note */}
      {item.review_note && item.status !== "draft" && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="py-3">
            <div className="text-xs font-medium text-amber-800 mb-1">검토 메모</div>
            <p className="text-sm text-amber-900">{item.review_note}</p>
          </CardContent>
        </Card>
      )}

      {/* Article body — 신문 스타일 */}
      <article className="rounded-xl border bg-card p-6 space-y-5">
        {/* AI 워터마크 */}
        <div className="flex items-center gap-1.5 rounded bg-amber-50 px-2.5 py-1 text-xs text-amber-900 border border-amber-200 w-fit">
          <Bot className="size-3.5" />
          AI 초안 — 편집자 검증 전{item.status === "approved" ? " (AI 초안 기반)" : ""}
        </div>
        <div className="border-b pb-4">
          {editing ? (
            <Input
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              className="text-2xl font-bold h-auto py-2"
              maxLength={300}
            />
          ) : (
            <h1 className="text-2xl font-bold leading-tight tracking-tight">
              {item.title}
            </h1>
          )}
          <div className="mt-2 text-xs text-muted-foreground">
            서울신문 편집국 · {new Date(item.created_at).toLocaleDateString("ko-KR")}
          </div>
        </div>

        {/* Lead */}
        <section>
          <h2 className="text-xs font-semibold uppercase text-muted-foreground mb-1.5">
            리드
          </h2>
          {editing ? (
            <textarea
              value={draftLead}
              onChange={(e) => setDraftLead(e.target.value)}
              className="w-full min-h-[80px] rounded border p-2 text-sm"
            />
          ) : (
            <p className="text-base font-medium leading-relaxed">{item.lead}</p>
          )}
        </section>

        {/* Body */}
        <section>
          <h2 className="text-xs font-semibold uppercase text-muted-foreground mb-1.5">
            본문
          </h2>
          {editing ? (
            <textarea
              value={draftBody}
              onChange={(e) => setDraftBody(e.target.value)}
              className="w-full min-h-[240px] rounded border p-2 text-sm font-mono"
            />
          ) : (
            <div className="prose prose-sm max-w-none whitespace-pre-wrap leading-relaxed">
              {item.body}
            </div>
          )}
        </section>

        {/* Background */}
        {(item.background || editing) && (
          <section>
            <h2 className="text-xs font-semibold uppercase text-muted-foreground mb-1.5">
              맥락 · 배경
            </h2>
            {editing ? (
              <textarea
                value={draftBackground}
                onChange={(e) => setDraftBackground(e.target.value)}
                className="w-full min-h-[100px] rounded border p-2 text-sm"
              />
            ) : (
              <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">
                {item.background}
              </p>
            )}
          </section>
        )}

        {/* Sources */}
        {item.sources.length > 0 && (
          <section className="border-t pt-4">
            <h2 className="text-xs font-semibold uppercase text-muted-foreground mb-2">
              출처
            </h2>
            <ul className="space-y-1 text-sm">
              {item.sources.map((s, i) => (
                <li key={i} className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-[10px]">
                    {s.name}
                  </Badge>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline truncate text-xs"
                  >
                    {s.url}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}
      </article>

      {/* Copy action */}
      <div className="flex gap-2">
        <CopyButton
          value={buildArticleMarkdown({
            title: item.title,
            subtitle: `서울신문 편집국 · ${new Date(item.created_at).toLocaleDateString("ko-KR")} · 상태: ${item.status}`,
            lead: item.lead,
            body: item.body,
            background: item.background,
            sources: item.sources,
          })}
          label="Markdown 복사"
          variant="outline"
        />
      </div>

      {/* RAG transparency */}
      {(item.references.length > 0 ||
        item.background_sources.length > 0 ||
        item.style_anchor) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <BookOpen className="size-4" />
              작성에 참고한 자료
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {item.references.length > 0 && (
              <div>
                <div className="text-xs font-semibold mb-1.5">인용 가능 참고</div>
                <ul className="space-y-1">
                  {item.references.map((r, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm">
                      <Badge variant="outline" className="text-[10px]">R{i + 1}</Badge>
                      <span className="font-medium">{r.name}</span>
                      <a
                        href={r.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline truncate flex items-center gap-1 text-xs"
                      >
                        {r.url}
                        <ExternalLink className="size-3" />
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {item.style_anchor && (
              <div className="flex items-start gap-2 rounded border border-dashed p-2 text-xs">
                <Sparkles className="size-3.5 text-amber-500 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-muted-foreground">톤 샘플</div>
                  <a
                    href={item.style_anchor.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline truncate block"
                  >
                    {item.style_anchor.url}
                  </a>
                </div>
              </div>
            )}
            {item.background_sources.length > 0 && (
              <div>
                <div className="text-xs font-semibold mb-1.5 text-muted-foreground">
                  경쟁 일간지 맥락 (직접 인용하지 않음)
                </div>
                <ul className="space-y-1">
                  {item.background_sources.map((b, i) => (
                    <li key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline" className="text-[10px]">{b.name}</Badge>
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
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function FactCheckCard({
  issues,
  onAck,
  totalAck,
}: {
  issues: FactIssue[];
  onAck: (issue: FactIssue, acknowledged: boolean) => void;
  totalAck: number;
}) {
  const total = issues.length;
  const sorted = [...issues].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
  );

  const allAck = totalAck === total && total > 0;
  const progressPct = total > 0 ? Math.round((totalAck / total) * 100) : 0;

  return (
    <Card className={allAck ? "border-emerald-300 bg-emerald-50/30" : ""}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {allAck ? (
            <ShieldCheck className="size-5 text-emerald-600" />
          ) : (
            <ShieldAlert className="size-5 text-amber-600" />
          )}
          자동 팩트 검증
          <Badge variant={allAck ? "default" : "outline"} className="text-[10px]">
            {totalAck}/{total} 확인
          </Badge>
          {allAck && (
            <span className="text-xs text-emerald-700 font-normal">
              모두 검토 완료
            </span>
          )}
        </CardTitle>
        {/* 진행바 */}
        <div className="h-1.5 w-full rounded-full bg-muted mt-2">
          <div
            className={`h-full rounded-full transition-all ${
              allAck ? "bg-emerald-500" : "bg-amber-500"
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {sorted.map((issue) => (
            <li
              key={issue.id}
              className={`rounded border p-3 ${SEV_COLOR[issue.severity]} ${
                issue.acknowledged ? "opacity-60" : ""
              }`}
            >
              <div className="flex items-start gap-2">
                <Badge className={`text-[10px] ${SEV_BADGE_COLOR[issue.severity]}`}>
                  {issue.severity.toUpperCase()}
                </Badge>
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="text-xs text-muted-foreground">
                    {KIND_LABEL[issue.kind]}
                  </div>
                  <div className="font-medium text-sm">
                    <span className="bg-yellow-100 px-1 rounded">
                      {issue.claim}
                    </span>
                  </div>
                  {issue.evidence && (
                    <div className="text-xs text-muted-foreground">
                      {issue.evidence}
                    </div>
                  )}
                  {issue.span_text && (
                    <div className="text-xs italic text-muted-foreground border-l-2 pl-2">
                      “{issue.span_text}”
                    </div>
                  )}
                  {issue.acknowledged && issue.acknowledged_note && (
                    <div className="text-xs text-emerald-700">
                      ✓ 확인 메모: {issue.acknowledged_note}
                    </div>
                  )}
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant={issue.acknowledged ? "secondary" : "outline"}
                  onClick={() => onAck(issue, !issue.acknowledged)}
                  className="shrink-0 gap-1"
                >
                  {issue.acknowledged ? (
                    <>
                      <ShieldCheck className="size-3.5" />
                      확인됨
                    </>
                  ) : (
                    <>
                      <ShieldAlert className="size-3.5" />
                      확인
                    </>
                  )}
                </Button>
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[11px] text-muted-foreground">
          ※ 자동 검증은 참고용입니다. 최종 판단은 편집자가 수행합니다.
          HIGH 등급 경고가 모두 확인되어야 승인이 가능합니다.
        </p>
      </CardContent>
    </Card>
  );
}

