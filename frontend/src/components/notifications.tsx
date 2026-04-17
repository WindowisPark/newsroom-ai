"use client";

import { useEffect, useState, useCallback } from "react";
import { Bell, X, Newspaper, BarChart3, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface Notification {
  id: string;
  type: string;
  message: string;
  time: Date;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const eventConfig: Record<string, { icon: typeof Bell; label: string }> = {
  new_articles: { icon: Newspaper, label: "새 기사 수집" },
  analysis_complete: { icon: BarChart3, label: "분석 완료" },
  report_generated: { icon: FileText, label: "리포트 생성" },
};

export function Notifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [connected, setConnected] = useState(false);

  const addNotification = useCallback((type: string, data: Record<string, unknown>) => {
    let message = "";
    if (type === "new_articles") {
      message = `새 기사 ${data.count ?? 0}건이 수집되었습니다.`;
    } else if (type === "analysis_complete") {
      message = `${data.count ?? 0}건의 기사 분석이 완료되었습니다.`;
    } else if (type === "report_generated") {
      const reportType = data.type === "briefing" ? "브리핑" : "의제 분석";
      message = `${reportType} 리포트가 자동 생성되었습니다.`;
    } else {
      message = `${type} 이벤트 발생`;
    }

    setNotifications((prev) => [
      { id: `${Date.now()}-${Math.random()}`, type, message, time: new Date() },
      ...prev.slice(0, 19),
    ]);
  }, []);

  useEffect(() => {
    let es: EventSource | null = null;
    let retryTimeout: ReturnType<typeof setTimeout>;

    function connect() {
      es = new EventSource(`${API_URL}/sse/stream`);

      es.onopen = () => setConnected(true);
      es.onerror = () => {
        setConnected(false);
        es?.close();
        retryTimeout = setTimeout(connect, 5000);
      };

      for (const eventType of Object.keys(eventConfig)) {
        es.addEventListener(eventType, (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data);
            addNotification(eventType, data);
          } catch {
            addNotification(eventType, {});
          }
        });
      }
    }

    connect();

    return () => {
      es?.close();
      clearTimeout(retryTimeout);
    };
  }, [addNotification]);

  const unreadCount = notifications.length;

  function clearAll() {
    setNotifications([]);
  }

  function removeOne(id: string) {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(!open)}
        className="relative"
      >
        <Bell className="size-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-80 rounded-xl border bg-popover shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">알림</span>
              <span
                className={`size-2 rounded-full ${connected ? "bg-emerald-500" : "bg-red-500"}`}
                title={connected ? "SSE 연결됨" : "연결 끊김"}
              />
            </div>
            {notifications.length > 0 && (
              <Button variant="ghost" size="xs" onClick={clearAll}>
                모두 지우기
              </Button>
            )}
          </div>
          <div className="max-h-72 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                알림이 없습니다.
              </p>
            ) : (
              notifications.map((n) => {
                const config = eventConfig[n.type] || { icon: Bell, label: n.type };
                const Icon = config.icon;
                return (
                  <div
                    key={n.id}
                    className="flex items-start gap-2.5 border-b px-3 py-2.5 last:border-0"
                  >
                    <div className="mt-0.5 rounded-md bg-muted p-1.5">
                      <Icon className="size-3.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm leading-snug">{n.message}</p>
                      <p className="mt-0.5 text-[10px] text-muted-foreground">
                        {n.time.toLocaleTimeString("ko-KR")}
                      </p>
                    </div>
                    <button
                      onClick={() => removeOne(n.id)}
                      className="mt-0.5 rounded p-0.5 text-muted-foreground hover:text-foreground"
                    >
                      <X className="size-3" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
