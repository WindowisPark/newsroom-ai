import { CheckCircle2, Clock, FileText, XCircle, type LucideIcon } from "lucide-react";

import type { ArticleDraftStatus } from "./types";

export const STATUS_LABEL: Record<ArticleDraftStatus, string> = {
  draft: "초안",
  in_review: "결재 대기",
  approved: "게시 완료",
  rejected: "반려",
};

export const STATUS_BADGE_CLASS: Record<ArticleDraftStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  in_review: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-destructive/10 text-destructive",
};

export const STATUS_TAB: Record<
  ArticleDraftStatus,
  { tabLabel: string; icon: LucideIcon; color: string }
> = {
  draft: { tabLabel: "내 초안", icon: FileText, color: "text-muted-foreground" },
  in_review: { tabLabel: "결재 대기", icon: Clock, color: "text-amber-600" },
  approved: { tabLabel: "게시 완료", icon: CheckCircle2, color: "text-emerald-600" },
  rejected: { tabLabel: "반려", icon: XCircle, color: "text-destructive" },
};
