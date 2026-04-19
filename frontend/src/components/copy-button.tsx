"use client";

import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCopyFeedback } from "@/lib/clipboard";
import { cn } from "@/lib/utils";

interface CopyButtonProps {
  value: string;
  label?: string;
  size?: "sm" | "default" | "icon";
  variant?: "default" | "ghost" | "outline" | "secondary";
  className?: string;
}

export function CopyButton({
  value,
  label,
  size = "sm",
  variant = "ghost",
  className,
}: CopyButtonProps) {
  const { copied, copy } = useCopyFeedback();

  const handleClick = () => {
    void copy(value);
  };

  // size="icon" 이면 아이콘만 (라벨 숨김)
  const showLabel = size !== "icon";
  const displayLabel = copied ? "복사됨" : (label ?? "복사");

  return (
    <Button
      type="button"
      size={size}
      variant={variant}
      onClick={handleClick}
      className={cn("gap-1.5", className)}
      aria-label={copied ? "복사됨" : (label ?? "복사")}
    >
      {copied ? (
        <Check className="size-3.5 text-green-600" />
      ) : (
        <Copy className="size-3.5" />
      )}
      {showLabel && <span>{displayLabel}</span>}
    </Button>
  );
}
