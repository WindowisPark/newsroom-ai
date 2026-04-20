// 신문 섹션 관례에 따른 카테고리 나열 순서.
export const CATEGORY_ORDER = [
  "politics",
  "economy",
  "society",
  "world",
  "tech",
  "culture",
  "sports",
] as const;

export const CATEGORY_LABEL: Record<string, string> = {
  politics: "정치",
  economy: "경제",
  society: "사회",
  world: "국제",
  tech: "기술",
  culture: "문화",
  sports: "스포츠",
};
