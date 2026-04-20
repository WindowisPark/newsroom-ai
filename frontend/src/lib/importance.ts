import type { Article } from "./types";

// importance_score 가 이 값 이상이면 '중요 기사' 로 취급 — 카드 강조, 배지.
export const HIGH_IMPORTANCE = 8.0;

export function isHighImportance(article: Pick<Article, "analysis">): boolean {
  return (article.analysis?.importance_score ?? 0) >= HIGH_IMPORTANCE;
}
