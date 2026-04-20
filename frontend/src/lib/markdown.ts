export interface ArticleMarkdownInput {
  title: string;
  subtitle?: string;
  lead: string;
  body: string;
  background?: string;
  sources?: { name: string; url: string }[];
  references?: { name: string; url: string; published_at?: string | null }[];
}

export function buildArticleMarkdown(input: ArticleMarkdownInput): string {
  const parts: string[] = [];
  parts.push(`# ${input.title}`);
  if (input.subtitle) {
    parts.push(`> ${input.subtitle}`);
  }
  parts.push("");
  parts.push(input.lead);
  parts.push("");
  parts.push(input.body);
  if (input.background) {
    parts.push("");
    parts.push("## 맥락 · 배경");
    parts.push(input.background);
  }
  if (input.sources && input.sources.length > 0) {
    parts.push("");
    parts.push("## 출처");
    parts.push(...input.sources.map((s) => `- ${s.name}: ${s.url}`));
  }
  if (input.references && input.references.length > 0) {
    parts.push("");
    parts.push("## 참고한 자사 기사 (RAG)");
    parts.push(
      ...input.references.map(
        (r) =>
          `- ${r.name}${r.published_at ? ` (${r.published_at.slice(0, 10)})` : ""}: ${r.url}`,
      ),
    );
  }
  return parts.join("\n");
}
