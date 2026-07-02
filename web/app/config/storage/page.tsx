"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AgentConfig } from "@/lib/types";
import { useState, useEffect } from "react";
import { Save, CheckCircle } from "lucide-react";

export default function StorageConfigPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.get<AgentConfig>("/api/config"),
  });

  const [form, setForm] = useState({
    LOGS_DIR: "/app/logs",
    ALERT_CATALOG_PATH: "/app/config/alert_catalog.yaml",
    ROUTING_CONFIG_PATH: "/app/alert-agent/routing.yaml",
    DEDUP_TTL_SECONDS: "900",
    ALLOWED_ALERTNAMES: "",
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setForm({
        LOGS_DIR: data.LOGS_DIR ?? "/app/logs",
        ALERT_CATALOG_PATH: data.ALERT_CATALOG_PATH ?? "/app/config/alert_catalog.yaml",
        ROUTING_CONFIG_PATH: data.ROUTING_CONFIG_PATH ?? "/app/alert-agent/routing.yaml",
        DEDUP_TTL_SECONDS: String(data.DEDUP_TTL_SECONDS ?? 900),
        ALLOWED_ALERTNAMES: data.ALLOWED_ALERTNAMES ?? "",
      });
    }
  }, [data]);

  const mutation = useMutation({
    // Post only changed fields to avoid pinning env-derived values.
    mutationFn: () => {
      const changed: Record<string, unknown> = {};
      if (form.LOGS_DIR !== (data?.LOGS_DIR ?? "")) changed.LOGS_DIR = form.LOGS_DIR;
      if (form.ALERT_CATALOG_PATH !== (data?.ALERT_CATALOG_PATH ?? "")) changed.ALERT_CATALOG_PATH = form.ALERT_CATALOG_PATH;
      if (form.ROUTING_CONFIG_PATH !== (data?.ROUTING_CONFIG_PATH ?? "")) changed.ROUTING_CONFIG_PATH = form.ROUTING_CONFIG_PATH;
      if (form.DEDUP_TTL_SECONDS !== String(data?.DEDUP_TTL_SECONDS ?? "")) changed.DEDUP_TTL_SECONDS = parseInt(form.DEDUP_TTL_SECONDS, 10);
      if (form.ALLOWED_ALERTNAMES !== (data?.ALLOWED_ALERTNAMES ?? "")) changed.ALLOWED_ALERTNAMES = form.ALLOWED_ALERTNAMES;
      return api.post("/api/config", changed);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  if (isLoading) return <div className="card h-64 animate-pulse" />;

  const field = (key: keyof typeof form, label: string, hint?: string, type = "text") => (
    <div key={key}>
      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{label}</label>
      <input
        className="input"
        type={type}
        value={form[key]}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
      />
      {hint && <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{hint}</p>}
    </div>
  );

  return (
    <div className="max-w-xl">
      <div className="mb-6">
        <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">Storage & Behavior</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">File paths, dedup window, and alert filtering.</p>
      </div>

      <div className="card space-y-5">
        {field("LOGS_DIR", "Logs directory", "Absolute path where RCA and incoming alert logs are written.")}
        {field("ALERT_CATALOG_PATH", "Alert catalog path", "YAML file mapping alertnames to business meanings.")}
        {field("ROUTING_CONFIG_PATH", "Routing config path", "YAML file for Slack routing rules.")}
        {field("DEDUP_TTL_SECONDS", "Dedup TTL (seconds)", "Duplicate alerts within this window are suppressed. Default: 900 (15 min).", "number")}
        {field("ALLOWED_ALERTNAMES", "Allowed alertnames (regex)", "Only alert names matching this pattern are processed. Leave blank to allow all.")}

        <div className="flex items-center gap-3 pt-2 border-t border-slate-100 dark:border-slate-700">
          <button className="btn-primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            <Save size={14} />
            {mutation.isPending ? "Saving…" : "Save changes"}
          </button>
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
              <CheckCircle size={14} /> Saved
            </span>
          )}
          {mutation.isError && (
            <span className="text-sm text-red-600 dark:text-red-400">{(mutation.error as Error).message}</span>
          )}
        </div>
      </div>
    </div>
  );
}
