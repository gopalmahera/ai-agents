"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { LogEntry } from "@/lib/types";
import { useState } from "react";
import { Search, Eye, Trash2, X, RefreshCw } from "lucide-react";

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

export default function LogsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"" | "rca" | "incoming">("");
  const [viewing, setViewing] = useState<string | null>(null);

  const { data: logs, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["logs", search, typeFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search) params.set("q", search);
      if (typeFilter) params.set("type", typeFilter);
      return api.get<LogEntry[]>(`/api/v1/logs?${params}`);
    },
  });

  const { data: fileContent } = useQuery({
    queryKey: ["log-file", viewing],
    queryFn: () => api.get<string>(`/api/v1/logs/${viewing}`),
    enabled: !!viewing,
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.delete(`/api/v1/logs/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["logs"] }),
  });

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">Logs</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Browse and view alert RCA and incoming log files.</p>
        </div>
        <button className="btn-ghost" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-48">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input pl-8" placeholder="Search by alert name…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select className="input w-36 flex-none" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as "" | "rca" | "incoming")}>
          <option value="">All types</option>
          <option value="rca">RCA</option>
          <option value="incoming">Incoming</option>
        </select>
      </div>

      <div className="card overflow-hidden !p-0">
        {isLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-10 bg-slate-100 dark:bg-slate-700 rounded animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-700">
                  <th className="px-5 py-3 font-medium">Timestamp</th>
                  <th className="px-5 py-3 font-medium">Alert</th>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium text-right">Size</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {(logs ?? []).map((log) => (
                  <tr key={log.name} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                    <td className="px-5 py-3 text-slate-500 dark:text-slate-400 font-mono text-xs whitespace-nowrap">
                      {log.timestamp.replace("T", " ").slice(0, 19)}
                    </td>
                    <td className="px-5 py-3 text-slate-700 dark:text-slate-300 font-mono text-xs">{log.alertname}</td>
                    <td className="px-5 py-3">
                      {log.type === "rca" ? <span className="badge-green">RCA</span> : <span className="badge-gray">incoming</span>}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-400 dark:text-slate-500 text-xs">{formatBytes(log.size)}</td>
                    <td className="px-5 py-3">
                      <div className="flex gap-1 justify-end">
                        <button className="btn-ghost p-1.5 text-xs" onClick={() => setViewing(log.name)}>
                          <Eye size={12} />
                        </button>
                        <button
                          className="btn-ghost p-1.5 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30"
                          onClick={() => { if (confirm(`Delete ${log.name}?`)) deleteMutation.mutate(log.name); }}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {(logs ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-12 text-center text-slate-400 dark:text-slate-500">
                      No log files found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {viewing && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 sm:p-6">
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-xl">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-slate-700">
              <p className="text-sm font-mono text-slate-700 dark:text-slate-300 truncate">{viewing}</p>
              <button className="btn-ghost p-1.5 shrink-0 ml-2" onClick={() => setViewing(null)}>
                <X size={14} />
              </button>
            </div>
            <pre className="flex-1 overflow-auto p-5 text-xs font-mono text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
              {typeof fileContent === "string" ? fileContent : JSON.stringify(fileContent, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
