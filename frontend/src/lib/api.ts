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

// SSE
export function createEventSource() {
  return new EventSource(`${BASE_URL}/sse/stream`);
}
