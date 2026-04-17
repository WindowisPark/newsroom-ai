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
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/news", label: "뉴스", icon: Newspaper },
  { href: "/analysis", label: "분석", icon: BarChart3 },
  { href: "/reports", label: "리포트", icon: FileText },
  { href: "/headlines", label: "기사 작성", icon: PenTool },
  { href: "/system", label: "시스템", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-56 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <Newspaper className="size-5 text-primary" />
        <span className="text-base font-semibold">Newsroom AI</span>
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
