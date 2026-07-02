"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, useEffect } from "react";
import { Plus, Trash2, Save, CheckCircle, Copy, Check, Layers } from "lucide-react";
import { api } from "@/lib/api";
import type { EndpointsConfig, EnvironmentsConfig, EndpointType } from "@/lib/types";
import {
  fromEnvConfig,
  toEnvConfig,
  validateEnvironments,
  type EditableEnv,
} from "@/lib/environments-validation";
import { toEnvironmentsYaml } from "@/lib/environments-yaml";

const AGENT_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const SOURCES: { field: keyof EditableEnv; type: EndpointType; label: string }[] = [
  { field: "prometheus", type: "prometheus", label: "Prometheus" },
  { field: "loki", type: "loki", label: "Loki" },
  { field: "kubernetes", type: "kubernetes", label: "Kubernetes" },
  { field: "aws", type: "aws", label: "AWS (CloudWatch)" },
];

function WebhookUrl({ name }: { name: string }) {
  const [copied, setCopied] = useState(false);
  const url = `${AGENT_BASE}/webhook/${name || "<name>"}`;
  const copy = () => {
    navigator.clipboard?.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <div className="flex items-center gap-2">
      <code className="flex-1 truncate rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-3 py-2 text-xs text-slate-700 dark:text-slate-300">
        {url}
      </code>
      <button className="btn-ghost" onClick={copy} disabled={!name} aria-label="Copy webhook URL">
        {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
      </button>
    </div>
  );
}

export default function EnvironmentsPage() {
  const qc = useQueryClient();
  const envQuery = useQuery({
    queryKey: ["environments"],
    queryFn: () => api.get<EnvironmentsConfig>("/api/config/environments"),
  });
  const epQuery = useQuery({
    queryKey: ["endpoints"],
    queryFn: () => api.get<EndpointsConfig>("/api/config/endpoints"),
  });

  const [envs, setEnvs] = useState<EditableEnv[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (envQuery.data) setEnvs(fromEnvConfig(envQuery.data));
  }, [envQuery.data]);

  const endpoints = epQuery.data?.endpoints ?? [];
  const byType = useMemo(() => {
    const map: Record<string, string> = {};
    for (const e of endpoints) if (e.name) map[e.name] = e.type;
    return map;
  }, [endpoints]);

  const validation = validateEnvironments(envs, byType);
  const yamlPreview = useMemo(() => toEnvironmentsYaml(toEnvConfig(envs)), [envs]);

  const mutation = useMutation({
    mutationFn: () => api.post<{ status: string }>("/api/config/environments", toEnvConfig(envs)),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      qc.invalidateQueries({ queryKey: ["environments"] });
    },
  });

  const patch = (id: string, p: Partial<EditableEnv>) =>
    setEnvs((prev) => prev.map((e) => (e.id === id ? { ...e, ...p } : e)));
  const remove = (id: string) => setEnvs((prev) => prev.filter((e) => e.id !== id));
  const add = () =>
    setEnvs((prev) => [
      ...prev,
      { id: `env-new-${Date.now()}-${prev.length}`, name: "", prometheus: "", loki: "", kubernetes: "", aws: "" },
    ]);

  if (envQuery.isLoading) return <div className="card h-64 animate-pulse" />;

  const hasDefault = envs.some((e) => e.name.trim() === "default");

  return (
    <div className="grid lg:grid-cols-[1fr_20rem] gap-6 items-start">
      <div>
        <div className="mb-6">
          <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">Environments</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Each environment maps a webhook path to a set of named endpoints. Point each cluster&apos;s
            Alertmanager at its <code className="text-xs">/webhook/&lt;name&gt;</code>. Bare
            <code className="text-xs"> /webhook</code> uses the <b>default</b> environment.
          </p>
        </div>

        {!hasDefault && (
          <div className="badge-yellow mb-4">Tip: add an environment named “default” for bare /webhook posts.</div>
        )}

        <div className="space-y-4">
          {envs.map((env) => (
            <div key={env.id} className="card space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Name</label>
                  <input className="input" value={env.name} placeholder="prod-ap-south-1"
                    onChange={(e) => patch(env.id, { name: e.target.value })} />
                </div>
                <button className="btn-ghost text-red-500 mt-6" onClick={() => remove(env.id)} aria-label="Remove environment">
                  <Trash2 size={15} />
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Webhook URL</label>
                <WebhookUrl name={env.name.trim()} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                {SOURCES.map(({ field, type, label }) => {
                  const options = endpoints.filter((e) => e.type === type);
                  return (
                    <div key={field}>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{label}</label>
                      <select className="input" value={String(env[field] ?? "")}
                        onChange={(e) => patch(env.id, { [field]: e.target.value } as Partial<EditableEnv>)}>
                        <option value="">— none (use default) —</option>
                        {options.map((o) => (
                          <option key={o.name} value={o.name}>{o.name}</option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>

              {validation.envs[env.id] && (
                <p className="text-sm text-red-600 dark:text-red-400">{validation.envs[env.id]}</p>
              )}
            </div>
          ))}
          {envs.length === 0 && (
            <div className="card text-sm text-slate-500 dark:text-slate-400 flex items-center gap-2">
              <Layers size={15} /> No environments yet — add one below.
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 mt-5">
          <button className="btn-secondary" onClick={add}><Plus size={14} /> Add environment</button>
          <button className="btn-primary" onClick={() => mutation.mutate()} disabled={!validation.valid || mutation.isPending}>
            <Save size={15} /> {mutation.isPending ? "Saving…" : "Save"}
          </button>
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
              <CheckCircle size={15} /> Saved
            </span>
          )}
          {mutation.error && <span className="text-sm text-red-600 dark:text-red-400">{(mutation.error as Error).message}</span>}
        </div>
        {endpoints.length === 0 && (
          <p className="text-xs text-amber-600 dark:text-amber-400 mt-3">
            No endpoints defined yet — add some under Endpoint Management to populate these dropdowns.
          </p>
        )}
      </div>

      <div className="card sticky top-20">
        <h2 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">YAML preview</h2>
        <pre className="text-xs text-slate-600 dark:text-slate-400 overflow-auto max-h-[70vh] whitespace-pre-wrap">{yamlPreview}</pre>
      </div>
    </div>
  );
}
