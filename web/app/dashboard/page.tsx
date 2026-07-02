"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { MetricsStats, McpHealth } from "@/lib/types";
import { Activity, CheckCircle, XCircle, Zap, AlertTriangle, RefreshCw, Database } from "lucide-react";

function StatCard({ label, value, icon: Icon, sub }: {
  label: string; value: number | string; icon: React.ElementType; sub?: string;
}) {
  return (
    <div className="card">
      <div className="flex items-start gap-4">
        <div className="w-9 h-9 rounded-lg bg-primary/10 dark:bg-primary/20 flex items-center justify-center shrink-0">
          <Icon size={16} className="text-primary dark:text-indigo-400" />
        </div>
        <div>
          <p className="text-2xl font-[Poppins] font-bold text-slate-900 dark:text-slate-100">{value}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
          {sub && <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

function McpStatusRow({ health }: { health?: McpHealth }) {
  const SERVICES = [
    { key: "K8S_MCP_URL", label: "K8s" },
    { key: "PROMETHEUS_MCP_URL", label: "Prometheus" },
    { key: "LOKI_MCP_URL", label: "Loki" },
    { key: "KAFKA_MCP_URL", label: "Kafka" },
  ];
  return (
    <div className="card">
      <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">MCP Server Status</h2>
      <div className="flex flex-wrap gap-4">
        {SERVICES.map(({ key, label }) => {
          const entry = health?.[key];
          return (
            <div key={key} className="flex items-center gap-1.5 text-sm">
              {entry?.status === "healthy" ? (
                <CheckCircle size={13} className="text-emerald-500" />
              ) : entry ? (
                <XCircle size={13} className="text-red-500" />
              ) : (
                <span className="w-3 h-3 rounded-full bg-slate-300 dark:bg-slate-600 inline-block" />
              )}
              <span className="text-slate-500 dark:text-slate-400">{label}</span>
            </div>
          );
        })}
      </div>
      {!health && (
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">
          Go to Config → MCP Services and click &quot;Check health&quot; to see status.
        </p>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["metrics-stats"],
    queryFn: () => api.get<MetricsStats>("/api/metrics/stats"),
    refetchInterval: 60_000,
  });

  const { data: health } = useQuery({
    queryKey: ["mcp-health"],
    queryFn: () => api.get<McpHealth>("/api/config/mcp/health"),
    staleTime: Infinity,
  });

  const { data: redisHealth } = useQuery({
    queryKey: ["redis-health"],
    queryFn: () => api.get<{ status: string }>("/api/redis/health").catch(() => ({ status: "unavailable" })),
    refetchInterval: 30_000,
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Live metrics from the running agent.</p>
        </div>
        <button className="btn-ghost" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card h-24 animate-pulse bg-slate-100 dark:bg-slate-800" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard label="Alerts Received" value={stats?.alerts_received ?? 0} icon={Activity} />
          <StatCard label="Alerts Accepted" value={stats?.alerts_accepted ?? 0} icon={CheckCircle} />
          <StatCard
            label="LLM Investigations"
            value={stats?.llm_investigations.success ?? 0}
            icon={Zap}
            sub={`${stats?.llm_investigations.error ?? 0} errors`}
          />
          <StatCard
            label="Deduplicated"
            value={stats?.alerts_deduplicated ?? 0}
            icon={AlertTriangle}
            sub={`${stats?.alerts_skipped ?? 0} skipped`}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <McpStatusRow health={health} />

        <div className="card flex items-center gap-3">
          <Database size={14} className={redisHealth?.status === "ok" ? "text-emerald-500" : "text-red-500"} />
          <div>
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Redis Store</p>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {redisHealth?.status === "ok"
                ? "Connected — data persists across restarts"
                : "Unavailable — metrics are in-memory only"}
            </p>
          </div>
        </div>
      </div>

      {stats && Object.keys(stats.by_alertname).length > 0 && (
        <div className="card">
          <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-4">Alerts by name</h2>
          <div className="space-y-2">
            {Object.entries(stats.by_alertname)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 10)
              .map(([name, count]) => (
                <div key={name} className="flex items-center gap-3">
                  <span className="text-sm text-slate-500 dark:text-slate-400 w-48 truncate font-mono text-xs">{name}</span>
                  <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${(count / (stats.alerts_received || 1)) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300 w-8 text-right">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
