"use client";

import { useCallback, useState } from "react";

export async function copyToClipboard(text: string): Promise<boolean> {
  if (typeof navigator === "undefined" || !navigator.clipboard) {
    return false;
  }
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * 1회 복사 + N ms 동안 "복사됨" 상태 노출 후 자동 원복.
 * 버튼/아이콘 UX 에서 재사용.
 */
export function useCopyFeedback(resetAfterMs = 1200) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(
    async (text: string) => {
      const ok = await copyToClipboard(text);
      if (ok) {
        setCopied(true);
        setTimeout(() => setCopied(false), resetAfterMs);
      }
      return ok;
    },
    [resetAfterMs]
  );

  return { copied, copy };
}
