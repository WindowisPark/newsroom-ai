export interface Meta {
  total: number;
  page: number;
  limit: number;
}

export interface APIResponse<T> {
  status: string;
  data: T;
  meta?: Meta;
}

export interface Entity {
  name: string;
  type: "person" | "organization" | "location";
}

export interface Analysis {
  category: string;
  keywords: string[];
  entities: Entity[];
  sentiment: "positive" | "negative" | "neutral";
  importance_score: number;
}

export interface Article {
  id: string;
  title: string;
  description: string;
  content: string | null;
  url: string;
  source_name: string;
  source_type: "domestic" | "foreign";
  published_at: string;
  collected_at: string;
  analysis: Analysis | null;
}

export interface CollectResult {
  collected_count: number;
  new_count: number;
  duplicate_count: number;
  sources: Record<string, number>;
}

export interface AgendaIssue {
  rank: number;
  topic: string;
  summary: string;
  importance_score: number;
  article_count: number;
  source_count: number;
  trend: string;
  categories: string[];
  key_keywords: string[];
  related_article_ids: string[];
}

export interface AgendaData {
  date: string;
  generated_at: string;
  top_issues: AgendaIssue[];
  analysis_summary: string;
}

export interface ArticleBrief {
  id: string;
  title: string;
  source_name: string;
  url: string;
}

export interface PerspectiveSide {
  frame: string;
  tone: string;
  key_points: string[];
  representative_articles: ArticleBrief[];
}

export interface PerspectiveComparison {
  frame_difference: string;
  background_context: string;
  editorial_insight: string;
}

export interface PerspectiveData {
  topic: string;
  generated_at: string;
  domestic: PerspectiveSide;
  foreign: PerspectiveSide;
  comparison: PerspectiveComparison;
}

export interface TrendDataPoint {
  time: string;
  count: number;
}

export interface TrendSeries {
  label: string;
  values: TrendDataPoint[];
}

export interface TrendData {
  period: string;
  type: string;
  data_points: TrendSeries[];
}

export interface BriefingSection {
  category: string;
  title: string;
  content: string;
}

export interface BriefingContent {
  headline: string;
  summary: string;
  sections: BriefingSection[];
}

export interface BriefingData {
  id: string;
  date: string;
  generated_at: string;
  briefing: BriefingContent;
  model_used: string;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface HeadlineItem {
  headline: string;
  reason: string;
  tone: string;
}

export interface HeadlineData {
  topic: string;
  generated_at: string;
  headlines: HeadlineItem[];
}

export interface TimelineEvent {
  date: string;
  event: string;
  significance: string;
}

export interface TimelineData {
  topic: string;
  generated_at: string;
  timeline: TimelineEvent[];
  context_summary: string;
}

export interface HealthData {
  status: string;
  version: string;
  database: string;
  scheduler: string;
  last_collection: string;
}

export interface SchedulerData {
  running: boolean;
  interval_minutes: number;
  next_run: string;
  last_run: string;
  total_collections: number;
}
