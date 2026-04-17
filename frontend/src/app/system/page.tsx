"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  RefreshCw,
  Activity,
  Database,
  Clock,
  Timer,
  AlertCircle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { getHealth, getSchedulerStatus } from "@/lib/api";
import type { HealthData, SchedulerData } from "@/lib/types";

export default function SystemPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [scheduler, setScheduler] = useState<SchedulerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [h, s] = await Promise.allSettled([getHealth(), getSchedulerStatus()]);
      if (h.status === "fulfilled") setHealth(h.value.data);
      if (s.status === "fulfilled") setScheduler(s.value.data);
      if (h.status === "rejected" && s.status === "rejected") {
        setError("시스템 상태를 확인할 수 없습니다. 백엔드가 실행 중인지 확인하세요.");
      }
    } catch {
      setError("시스템 상태를 확인할 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">시스템</h1>
          <p className="text-sm text-muted-foreground">서버 상태 및 스케줄러 모니터링</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
          새로고침
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {/* Health */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="size-4" /> 서버 상태
              </CardTitle>
            </CardHeader>
            <CardContent>
              {health ? (
                <div className="space-y-3">
                  <StatusRow
                    label="상태"
                    value={health.status === "ok" ? "정상" : health.status}
                    ok={health.status === "ok"}
                  />
                  <StatusRow
                    label="데이터베이스"
                    value={health.database === "connected" ? "연결됨" : health.database}
                    ok={health.database === "connected"}
                  />
                  <StatusRow
                    label="스케줄러"
                    value={health.scheduler === "running" ? "실행 중" : health.scheduler}
                    ok={health.scheduler === "running"}
                  />
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">마지막 수집</span>
                    <span>
                      {health.last_collection
                        ? new Date(health.last_collection).toLocaleString("ko-KR")
                        : "—"}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">데이터 없음</p>
              )}
            </CardContent>
          </Card>

          {/* Scheduler */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Timer className="size-4" /> 스케줄러
              </CardTitle>
            </CardHeader>
            <CardContent>
              {scheduler ? (
                <div className="space-y-3">
                  <StatusRow
                    label="실행 상태"
                    value={scheduler.running ? "실행 중" : "중지됨"}
                    ok={scheduler.running}
                  />
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">수집 간격</span>
                    <span>{scheduler.interval_minutes}분</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">다음 실행</span>
                    <span>
                      {scheduler.next_run
                        ? new Date(scheduler.next_run).toLocaleTimeString("ko-KR")
                        : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">마지막 실행</span>
                    <span>
                      {scheduler.last_run
                        ? new Date(scheduler.last_run).toLocaleString("ko-KR")
                        : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">총 수집 횟수</span>
                    <Badge variant="secondary">{scheduler.total_collections}회</Badge>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">데이터 없음</p>
              )}
            </CardContent>
          </Card>

          {/* API Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="size-4" /> API 정보
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">베이스 URL</span>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}
                  </code>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">버전</span>
                  <span>{health?.version || "—"}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Connection Test */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="size-4" /> 연결 테스트
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <StatusRow
                  label="백엔드 연결"
                  value={health ? "정상" : "실패"}
                  ok={!!health}
                />
                <StatusRow
                  label="DB 연결"
                  value={health?.database === "connected" ? "정상" : "실패"}
                  ok={health?.database === "connected"}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="flex items-center gap-1.5">
        {ok ? (
          <CheckCircle2 className="size-3.5 text-emerald-500" />
        ) : (
          <XCircle className="size-3.5 text-red-500" />
        )}
        {value}
      </span>
    </div>
  );
}
