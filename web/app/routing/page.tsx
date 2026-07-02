"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RoutingConfig, RoutingRule } from "@/lib/types";
import { useState, useEffect } from "react";
import { Plus, Trash2, Save, CheckCircle } from "lucide-react";

function RuleRow({ rule, onChange, onDelete }: {
  rule: RoutingRule; onChange: (r: RoutingRule) => void; onDelete: () => void;
}) {
  const parseJson = (s: string): Record<string, string> => { try { return JSON.parse(s); } catch { return {}; } };

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-xl p-4 space-y-3 bg-slate-50 dark:bg-slate-800/50">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">match (exact labels JSON)</label>
          <input
            className="input text-xs font-mono"
            defaultValue={JSON.stringify(rule.match ?? {})}
            onBlur={(e) => onChange({ ...rule, match: parseJson(e.target.value) })}
            placeholder='{"alertname":"PodCrash"}'
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">match_re (regex labels JSON)</label>
          <input
            className="input text-xs font-mono"
            defaultValue={JSON.stringify(rule.match_re ?? {})}
            onBlur={(e) => onChange({ ...rule, match_re: parseJson(e.target.value) })}
            placeholder='{"namespace":"^prod"}'
          />
        </div>
      </div>
      <div className="flex gap-2 items-end">
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Slack webhook URL</label>
          <input
            className="input"
            value={rule.slack_webhook_url}
            onChange={(e) => onChange({ ...rule, slack_webhook_url: e.target.value })}
            placeholder="https://hooks.slack.com/services/…"
          />
        </div>
        <button className="btn-ghost p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 shrink-0" onClick={onDelete}>
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

export default function RoutingPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["routing"],
    queryFn: () => api.get<RoutingConfig>("/api/config/routing"),
  });

  const [defaultUrl, setDefaultUrl] = useState("");
  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) { setDefaultUrl(data.default_slack_webhook_url ?? ""); setRules(data.routes ?? []); }
  }, [data]);

  const mutation = useMutation({
    mutationFn: () => api.post("/api/config/routing", { default_slack_webhook_url: defaultUrl, routes: rules }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["routing"] }); setSaved(true); setTimeout(() => setSaved(false), 2500); },
  });

  if (isLoading) return <div className="card h-64 animate-pulse" />;

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">Routing Rules</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Routes are evaluated top-to-bottom. First matching rule wins.
        </p>
      </div>

      <div className="card mb-4">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Default Slack webhook URL</label>
        <input className="input" value={defaultUrl} onChange={(e) => setDefaultUrl(e.target.value)} placeholder="https://hooks.slack.com/services/…" />
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Used when no route matches.</p>
      </div>

      <div className="space-y-3 mb-4">
        {rules.map((rule, i) => (
          <RuleRow key={i} rule={rule} onChange={(r) => setRules((rs) => rs.map((x, j) => j === i ? r : x))} onDelete={() => setRules((rs) => rs.filter((_, j) => j !== i))} />
        ))}
        {rules.length === 0 && (
          <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-8 border border-dashed border-slate-200 dark:border-slate-700 rounded-xl">
            No routing rules — all alerts go to the default webhook.
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button className="btn-secondary" onClick={() => setRules((r) => [...r, { match: {}, slack_webhook_url: "" }])}>
          <Plus size={14} /> Add rule
        </button>
        <button className="btn-primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          <Save size={14} /> {mutation.isPending ? "Saving…" : "Save routing"}
        </button>
        {saved && <span className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400"><CheckCircle size={14} /> Saved</span>}
        {mutation.isError && <span className="text-sm text-red-600 dark:text-red-400">{(mutation.error as Error).message}</span>}
      </div>
    </div>
  );
}
