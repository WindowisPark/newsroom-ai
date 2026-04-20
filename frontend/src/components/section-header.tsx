import type { ReactNode } from "react";

// 신문 섹션 구분 규약 — 짧은 uppercase 라벨 + 오른쪽 메타/링크 슬롯.
// reports/page.tsx 의 번호(①②③) 헤더는 별도 타이포라 로컬 유지.
export function SectionHeader({
  label,
  meta,
  right,
}: {
  label: string;
  meta?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="mb-3 flex items-baseline justify-between border-b pb-1.5">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </h2>
      {right ?? (meta && <span className="text-xs text-muted-foreground">{meta}</span>)}
    </div>
  );
}
