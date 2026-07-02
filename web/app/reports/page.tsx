"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ReportSummary } from "@/lib/types";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { RefreshCw } from "lucide-react";
import { useState } from "react";

const DAYS_OPTIONS = [
  { label: "24h", value: 1 },
  { label: "7d", value: 7 },
  { label: "30d", value: 30 },
];

export default function ReportsPage() {
  const [days, setDays] = useState(7);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["reports-summary", days],
    queryFn: () => api.get<ReportSummary>(`/api/reports/summary?days=${days}`),
    refetchInterval: 120_000,
  });

  const timelineData = (data?.timeline ?? []).map((t) => ({
    hour: t.hour.slice(5, 16).replace("T", " "),
    count: t.count,
  }));

  const alertTableData = Object.entries(data?.by_alertname ?? {})
    .sort((a, b) => (b[1].rca + b[1].incoming) - (a[1].rca + a[1].incoming))
    .slice(0, 20);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">Reports</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Alert activity{data?.source === "mongo" ? " from MongoDB history" : " from Redis stream"}.
            {data && ` ${data.files} events in the last ${days === 1 ? "24h" : `${days}d`}`}
            {data?.totals ? ` · $${data.totals.cost_usd.toFixed(4)} LLM cost.` : "."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
            {DAYS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setDays(opt.value)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  days === opt.value
                    ? "bg-primary text-white"
                    : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <button className="btn-ghost" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <div className="card h-52 animate-pulse" />
          <div className="card h-64 animate-pulse" />
        </div>
      ) : (
        <div className="space-y-6">
          {timelineData.length > 0 && (
            <div className="card">
              <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-4">Alerts over time</h2>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={timelineData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="hour" tick={{ fontSize: 10 }} stroke="#94a3b8" interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", fontSize: 12, borderRadius: 8 }}
                  />
                  <Bar dataKey="count" fill="#4F46E5" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {alertTableData.length > 0 ? (
            <div className="card overflow-hidden !p-0">
              <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700">
                <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300">By alert name</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-700">
                      <th className="px-5 py-3 font-medium">Alert name</th>
                      <th className="px-5 py-3 font-medium text-right">RCA</th>
                      <th className="px-5 py-3 font-medium text-right">Received</th>
                      <th className="px-5 py-3 font-medium text-right">Total</th>
                      {data?.source === "mongo" && <th className="px-5 py-3 font-medium text-right">Cost</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                    {alertTableData.map(([name, counts]) => (
                      <tr key={name} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                        <td className="px-5 py-3 text-slate-700 dark:text-slate-300 font-mono text-xs">{name}</td>
                        <td className="px-5 py-3 text-right text-slate-500 dark:text-slate-400">{counts.rca}</td>
                        <td className="px-5 py-3 text-right text-slate-500 dark:text-slate-400">{counts.incoming}</td>
                        <td className="px-5 py-3 text-right font-medium text-slate-700 dark:text-slate-300">
                          {counts.rca + counts.incoming}
                        </td>
                        {data?.source === "mongo" && (
                          <td className="px-5 py-3 text-right text-slate-500 dark:text-slate-400">
                            ${(counts.cost_usd ?? 0).toFixed(4)}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="card text-center py-16">
              <p className="text-slate-500 dark:text-slate-400 text-sm">No alert events for the selected period.</p>
              <p className="text-slate-400 dark:text-slate-500 text-xs mt-1">Events are written when the agent processes alerts.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
