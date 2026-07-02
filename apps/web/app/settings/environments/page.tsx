"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Save, CheckCircle, Copy, Check, Layers } from "lucide-react";
import { api } from "@/lib/api";
import type { EndpointsConfig, EnvironmentsConfig, EndpointType } from "@/lib/types";
import {
  fromEnvConfig,
  toEnvConfig,
  validateEnvironments,
  type EditableEnv,
} from "@/lib/environments-validation";
import { SettingsPageLayout } from "@/components/settings/SettingsPageLayout";
import { SettingsToolbar } from "@/components/settings/SettingsToolbar";
import { SettingsCardGrid } from "@/components/settings/SettingsCardGrid";
import { SettingsEntityCard } from "@/components/settings/SettingsEntityCard";
import { SettingsDrawer } from "@/components/settings/SettingsDrawer";

const AGENT_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const SOURCES: { field: keyof EditableEnv; type: EndpointType; label: string }[] = [
  { field: "prometheus", type: "prometheus", label: "Prometheus" },
  { field: "loki", type: "loki", label: "Loki" },
  { field: "kubernetes", type: "kubernetes", label: "Kubernetes" },
  { field: "aws", type: "aws", label: "AWS" },
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
      <code className="flex-1 truncate rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-3 py-2 text-xs">
        {url}
      </code>
      <button className="btn-ghost" onClick={copy} disabled={!name}>
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

  const [search, setSearch] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<EditableEnv | null>(null);
  const [originalName, setOriginalName] = useState<string | undefined>();
  const [saved, setSaved] = useState(false);

  const envs = useMemo(() => fromEnvConfig(envQuery.data), [envQuery.data]);
  const endpoints = epQuery.data?.endpoints ?? [];
  const byType = useMemo(() => {
    const map: Record<string, string> = {};
    for (const e of endpoints) if (e.name) map[e.name] = e.type;
    return map;
  }, [endpoints]);

  const filtered = useMemo(() => {
    if (!search) return envs;
    const q = search.toLowerCase();
    return envs.filter((e) => e.name.toLowerCase().includes(q));
  }, [envs, search]);

  const validation = editing ? validateEnvironments([editing], byType) : { valid: true, envs: {} as Record<string, string> };

  const saveMutation = useMutation({
    mutationFn: async ({ env, originalName: orig }: { env: EditableEnv; originalName?: string }) => {
      const payload = toEnvConfig([env]).environments[0];
      if (orig) {
        await api.put(`/api/v1/settings/environments/${encodeURIComponent(orig)}`, payload);
      } else {
        await api.post("/api/v1/settings/environments", payload);
      }
    },
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      setDrawerOpen(false);
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["environments"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.delete(`/api/v1/settings/environments/${encodeURIComponent(name)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["environments"] }),
  });

  if (envQuery.isLoading) return <div className="card h-64 animate-pulse" />;

  const hasDefault = envs.some((e) => e.name.trim() === "default");

  return (
    <SettingsPageLayout
      title="Environments"
      description="Each environment maps a webhook path to named endpoints."
      toolbar={
        <SettingsToolbar
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search environments…"
          addLabel="Add environment"
          onAdd={() => {
            setOriginalName(undefined);
            setEditing({ id: `new-${Date.now()}`, name: "", prometheus: "", loki: "", kubernetes: "", aws: "" });
            setDrawerOpen(true);
          }}
        />
      }
    >
      {!hasDefault && (
        <div className="badge-yellow mb-4">Tip: add an environment named “default” for bare /webhook posts.</div>
      )}

      {filtered.length === 0 ? (
        <div className="card text-sm text-slate-500 flex items-center gap-2">
          <Layers size={15} /> No environments yet.
        </div>
      ) : (
        <SettingsCardGrid>
          {filtered.map((env) => (
            <SettingsEntityCard
              key={env.id}
              title={env.name || "(unnamed)"}
              subtitle={[env.prometheus, env.loki, env.kubernetes].filter(Boolean).join(" · ") || "No endpoints linked"}
              onClick={() => {
                setOriginalName(env.name.trim() || undefined);
                setEditing({ ...env });
                setDrawerOpen(true);
              }}
              onDelete={env.name ? () => deleteMutation.mutate(env.name.trim()) : undefined}
            />
          ))}
        </SettingsCardGrid>
      )}

      <SettingsDrawer
        open={drawerOpen && !!editing}
        title={editing?.name ? `Edit ${editing.name}` : "New environment"}
        onClose={() => { setDrawerOpen(false); setEditing(null); }}
        footer={
          <>
            <button className="btn-primary" disabled={!validation.valid || saveMutation.isPending || endpoints.length === 0}
              onClick={() => editing && saveMutation.mutate({ env: editing, originalName })}>
              <Save size={15} /> Save
            </button>
            {saved && <span className="text-sm text-emerald-600 flex items-center gap-1"><CheckCircle size={15} /> Saved</span>}
            {saveMutation.error && <span className="text-sm text-red-600">{(saveMutation.error as Error).message}</span>}
          </>
        }
      >
        {editing && (
          <>
            <div>
              <label className="block text-sm font-medium mb-1.5">Name</label>
              <input className="input" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Webhook URL</label>
              <WebhookUrl name={editing.name} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {SOURCES.map(({ field, type, label }) => {
                const options = endpoints.filter((e) => e.type === type);
                return (
                  <div key={field}>
                    <label className="block text-sm font-medium mb-1.5">{label}</label>
                    <select className="input" value={editing[field]} onChange={(e) => setEditing({ ...editing, [field]: e.target.value })}>
                      <option value="">— none —</option>
                      {options.map((o) => <option key={o.name} value={o.name}>{o.name}</option>)}
                    </select>
                  </div>
                );
              })}
            </div>
            {validation.envs[editing.id] && <p className="text-sm text-red-600">{validation.envs[editing.id]}</p>}
          </>
        )}
      </SettingsDrawer>
    </SettingsPageLayout>
  );
}
