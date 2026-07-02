"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AgentConfig, McpHealthEntry } from "@/lib/types";
import { useState, useEffect } from "react";
import { RefreshCw, Save, CheckCircle } from "lucide-react";

// ── Direct service endpoints (Prometheus, Loki) ───────────────────────────────
const DIRECT_SERVICES = [
  {
    key: "PROMETHEUS_URL",
    label: "Prometheus",
    hint: "Direct Prometheus API endpoint used for metric queries",
    placeholder: "http://prometheus-sit.dozee.int",
  },
  {
    key: "LOKI_URL",
    label: "Loki",
    hint: "Direct Loki endpoint used for log queries",
    placeholder: "http://host.docker.internal:3100",
  },
] as const;

// ── MCP proxy server URLs ─────────────────────────────────────────────────────
const MCP_SERVERS = [
  { key: "K8S_MCP_URL", label: "Kubernetes", placeholder: "http://127.0.0.1:8001/mcp" },
  { key: "PROMETHEUS_MCP_URL", label: "Prometheus", placeholder: "http://127.0.0.1:8002/mcp" },
  { key: "LOKI_MCP_URL", label: "Loki", placeholder: "http://127.0.0.1:8003/mcp" },
  { key: "KAFKA_MCP_URL", label: "Kafka", placeholder: "http://127.0.0.1:8004/mcp" },
] as const;

type AllKeys =
  | (typeof DIRECT_SERVICES)[number]["key"]
  | (typeof MCP_SERVERS)[number]["key"];

function StatusDot({ entry }: { entry?: McpHealthEntry }) {
  if (!entry) return <span className="inline-block w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600" />;
  if (entry.status === "healthy") return <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />;
  if (entry.status === "not_configured") return <span className="inline-block w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600" />;
  return <span className="inline-block w-2 h-2 rounded-full bg-red-500" />;
}

function StatusBadge({ entry }: { entry?: McpHealthEntry }) {
  if (!entry) return null;
  if (entry.status === "healthy") return <span className="badge-green">healthy</span>;
  if (entry.status === "not_configured") return <span className="badge-gray">not set</span>;
  if (entry.status === "unreachable") return <span className="badge-red">unreachable</span>;
  return <span className="badge-yellow">{entry.status}</span>;
}

export default function McpConfigPage() {
  const qc = useQueryClient();
  const { data: config, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.get<AgentConfig>("/api/config"),
  });

  const [urls, setUrls] = useState<Record<AllKeys, string>>({
    PROMETHEUS_URL: "",
    LOKI_URL: "",
    K8S_MCP_URL: "",
    PROMETHEUS_MCP_URL: "",
    LOKI_MCP_URL: "",
    KAFKA_MCP_URL: "",
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (config) {
      setUrls({
        PROMETHEUS_URL: config.PROMETHEUS_URL ?? "",
        LOKI_URL: config.LOKI_URL ?? "",
        K8S_MCP_URL: config.K8S_MCP_URL ?? "",
        PROMETHEUS_MCP_URL: config.PROMETHEUS_MCP_URL ?? "",
        LOKI_MCP_URL: config.LOKI_MCP_URL ?? "",
        KAFKA_MCP_URL: config.KAFKA_MCP_URL ?? "",
      });
    }
  }, [config]);

  // MCP proxy health
  const {
    data: mcpHealth,
    isFetching: mcpChecking,
    refetch: checkMcp,
  } = useQuery({
    queryKey: ["mcp-health"],
    queryFn: () => api.get<Record<string, McpHealthEntry>>("/api/config/mcp/health"),
    enabled: false,
  });

  // Direct service health
  const {
    data: svcHealth,
    isFetching: svcChecking,
    refetch: checkSvc,
  } = useQuery({
    queryKey: ["svc-health"],
    queryFn: () => api.get<Record<string, McpHealthEntry>>("/api/config/services/health"),
    enabled: false,
  });

  const saveMutation = useMutation({
    mutationFn: () => api.post("/api/config", urls),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const setUrl = (key: AllKeys, value: string) =>
    setUrls((u) => ({ ...u, [key]: value }));

  if (isLoading) {
    return (
      <div className="max-w-2xl space-y-4">
        <div className="h-7 w-48 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
        <div className="card h-40 animate-pulse" />
        <div className="card h-56 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">
          MCP & Service Config
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Configure direct service endpoints and MCP proxy server URLs used by the agent.
        </p>
      </div>

      {/* ── Section 1: Direct service endpoints ── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              Direct Service Endpoints
            </h2>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
              Raw API URLs queried directly by the agent (not via MCP).
            </p>
          </div>
          <button
            className="btn-secondary text-xs px-3 py-1.5"
            onClick={() => checkSvc()}
            disabled={svcChecking}
          >
            <RefreshCw size={12} className={svcChecking ? "animate-spin" : ""} />
            {svcChecking ? "Checking…" : "Check"}
          </button>
        </div>

        <div className="card divide-y divide-slate-100 dark:divide-slate-700">
          {DIRECT_SERVICES.map(({ key, label, hint, placeholder }) => (
            <div key={key} className="py-4 first:pt-0 last:pb-0">
              <div className="flex items-center gap-2 mb-1.5">
                <StatusDot entry={svcHealth?.[key]} />
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
                <StatusBadge entry={svcHealth?.[key]} />
                {svcHealth?.[key]?.error && (
                  <span className="text-xs text-red-500 truncate max-w-xs" title={svcHealth[key].error}>
                    — {svcHealth[key].error}
                  </span>
                )}
              </div>
              <input
                className="input"
                value={urls[key]}
                onChange={(e) => setUrl(key, e.target.value)}
                placeholder={placeholder}
              />
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{hint}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Section 2: MCP server URLs ── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              MCP Server URLs
            </h2>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
              FastMCP proxy servers that expose tools to the AI agent.
            </p>
          </div>
          <button
            className="btn-secondary text-xs px-3 py-1.5"
            onClick={() => checkMcp()}
            disabled={mcpChecking}
          >
            <RefreshCw size={12} className={mcpChecking ? "animate-spin" : ""} />
            {mcpChecking ? "Checking…" : "Check"}
          </button>
        </div>

        <div className="card divide-y divide-slate-100 dark:divide-slate-700">
          {MCP_SERVERS.map(({ key, label, placeholder }) => (
            <div key={key} className="py-4 first:pt-0 last:pb-0">
              <div className="flex items-center gap-2 mb-1.5">
                <StatusDot entry={mcpHealth?.[key]} />
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
                <StatusBadge entry={mcpHealth?.[key]} />
                {mcpHealth?.[key]?.error && (
                  <span className="text-xs text-red-500 truncate max-w-xs" title={mcpHealth[key].error}>
                    — {mcpHealth[key].error}
                  </span>
                )}
              </div>
              <input
                className="input font-mono text-xs"
                value={urls[key]}
                onChange={(e) => setUrl(key, e.target.value)}
                placeholder={placeholder}
              />
            </div>
          ))}
        </div>
      </div>

      {/* ── Save ── */}
      <div className="flex items-center gap-3">
        <button
          className="btn-primary"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
        >
          <Save size={14} />
          {saveMutation.isPending ? "Saving…" : "Save all"}
        </button>
        {saved && (
          <span className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
            <CheckCircle size={14} /> Saved
          </span>
        )}
        {saveMutation.isError && (
          <span className="text-sm text-red-600 dark:text-red-400">
            {(saveMutation.error as Error).message}
          </span>
        )}
      </div>
    </div>
  );
}
