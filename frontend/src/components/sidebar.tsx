"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Newspaper,
  BarChart3,
  FileText,
  PenTool,
  LayoutDashboard,
  Activity,
  Bookmark,
  NotebookPen,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/reports", label: "일일 브리핑", icon: FileText },
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/news", label: "뉴스", icon: Newspaper },
  { href: "/analysis", label: "분석", icon: BarChart3 },
  { href: "/headlines", label: "기사 작성", icon: PenTool },
  { href: "/newsroom", label: "편집실", icon: NotebookPen },
  { href: "/watchlist", label: "워치리스트", icon: Bookmark },
  { href: "/system", label: "시스템", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-56 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center gap-2.5 border-b px-4">
        <Newspaper className="size-4 shrink-0 text-primary" />
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-bold tracking-tight text-primary">서울신문</span>
          <span className="text-[9px] font-medium uppercase tracking-widest text-muted-foreground">
            AI 뉴스룸
          </span>
        </div>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
              )}
            >
              <item.icon className="size-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
