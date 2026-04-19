import type {
  APIResponse,
  Article,
  CollectResult,
  AgendaData,
  PerspectiveData,
  TrendData,
  BriefingData,
  HeadlineData,
  TimelineData,
  HealthData,
  SchedulerData,
  DraftData,
  DraftStyle,
  WatchlistItem,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<APIResponse<T>> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(error.message || `API error: ${res.status}`);
  }
  return res.json();
}

// News
export async function getNews(params?: Record<string, string>) {
  const query = params ? "?" + new URLSearchParams(params).toString() : "";
  return fetchAPI<Article[]>(`/news${query}`);
}

export async function getNewsDetail(id: string) {
  return fetchAPI<Article>(`/news/${id}`);
}

export async function collectNews(sources?: string[], query?: string) {
  return fetchAPI<CollectResult>("/news/collect", {
    method: "POST",
    body: JSON.stringify({ sources: sources || ["newsapi", "naver", "rss"], query }),
  });
}

// Analysis
export async function getAgenda(params?: Record<string, string>) {
  const query = params ? "?" + new URLSearchParams(params).toString() : "";
  return fetchAPI<AgendaData>(`/analysis/agenda${query}`);
}

export async function getPerspective(topic: string, date?: string) {
  const params = new URLSearchParams({ topic });
  if (date) params.set("date", date);
  return fetchAPI<PerspectiveData>(`/analysis/perspective?${params}`);
}

export async function getTrends(params?: Record<string, string>) {
  const query = params ? "?" + new URLSearchParams(params).toString() : "";
  return fetchAPI<TrendData>(`/analysis/trends${query}`);
}

// Reports
export async function getBriefing(date?: string) {
  const query = date ? `?date=${date}` : "";
  return fetchAPI<BriefingData>(`/reports/briefing${query}`);
}

export async function generateBriefing() {
  return fetchAPI<BriefingData>("/reports/briefing/generate", { method: "POST" });
}

// Headlines
export async function recommendHeadlines(topic: string, articleIds: string[], style = "neutral") {
  return fetchAPI<HeadlineData>("/headlines/recommend", {
    method: "POST",
    body: JSON.stringify({ topic, article_ids: articleIds, style }),
  });
}

export async function getTimeline(topic: string, articleIds: string[]) {
  return fetchAPI<TimelineData>("/headlines/timeline", {
    method: "POST",
    body: JSON.stringify({ topic, article_ids: articleIds }),
  });
}

// Dashboard
export async function getDashboardStats() {
  return fetchAPI<{
    total_articles_today: number;
    unanalyzed_count: number;
    high_importance_count: number;
    breaking_count: number;
    top_keywords: { keyword: string; count: number }[];
    category_distribution: Record<string, number>;
  }>("/dashboard/stats");
}

// System
export async function getHealth() {
  return fetchAPI<HealthData>("/health");
}

export async function getSchedulerStatus() {
  return fetchAPI<SchedulerData>("/system/scheduler");
}

// Drafts (기사 초안)
export async function generateDraft(
  articleIds: string[],
  style: DraftStyle = "straight",
  topicHint?: string
) {
  return fetchAPI<DraftData>("/drafts/generate", {
    method: "POST",
    body: JSON.stringify({
      article_ids: articleIds,
      style,
      topic_hint: topicHint,
    }),
  });
}

// Watchlist
export async function getWatchlist() {
  return fetchAPI<WatchlistItem[]>("/watchlist");
}

export async function addWatchlist(keyword: string) {
  return fetchAPI<WatchlistItem>("/watchlist", {
    method: "POST",
    body: JSON.stringify({ keyword }),
  });
}

export async function patchWatchlist(id: string, isActive: boolean) {
  return fetchAPI<WatchlistItem>(`/watchlist/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export async function deleteWatchlist(id: string) {
  return fetchAPI<{ deleted: boolean }>(`/watchlist/${id}`, {
    method: "DELETE",
  });
}

// SSE
export function createEventSource() {
  return new EventSource(`${BASE_URL}/sse/stream`);
}
