"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AgentConfig } from "@/lib/types";
import { useState, useEffect } from "react";
import { Save, Eye, EyeOff, CheckCircle } from "lucide-react";

const PROVIDERS = [
  { value: "openai", label: "OpenAI", defaultModel: "gpt-4o" },
  { value: "anthropic", label: "Anthropic", defaultModel: "claude-sonnet-5" },
  { value: "gemini", label: "Google Gemini", defaultModel: "gemini-2.0-flash" },
  { value: "bedrock", label: "AWS Bedrock", defaultModel: "us.anthropic.claude-sonnet-4-5" },
  { value: "fake", label: "Fake (echo)", defaultModel: "echo" },
];

export default function AIConfigPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.get<AgentConfig>("/api/config"),
  });

  const [form, setForm] = useState({ AI_PROVIDER: "openai", OPENAI_MODEL: "gpt-4o", OPENAI_API_KEY: "", LLM_ENABLED: true });
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setForm({
        AI_PROVIDER: data.AI_PROVIDER ?? "openai",
        OPENAI_MODEL: data.OPENAI_MODEL ?? "gpt-4o",
        OPENAI_API_KEY: data.OPENAI_API_KEY === "***" ? "" : (data.OPENAI_API_KEY ?? ""),
        LLM_ENABLED: data.LLM_ENABLED === true || data.LLM_ENABLED === "true",
      });
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: (body: Partial<AgentConfig>) => api.post("/api/config", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const handleProviderChange = (provider: string) => {
    const p = PROVIDERS.find((p) => p.value === provider);
    setForm((f) => ({ ...f, AI_PROVIDER: provider, OPENAI_MODEL: p?.defaultModel ?? f.OPENAI_MODEL }));
  };

  const handleSave = () => {
    const payload: Record<string, unknown> = {
      AI_PROVIDER: form.AI_PROVIDER,
      OPENAI_MODEL: form.OPENAI_MODEL,
      LLM_ENABLED: form.LLM_ENABLED,
    };
    if (form.OPENAI_API_KEY) payload.OPENAI_API_KEY = form.OPENAI_API_KEY;
    mutation.mutate(payload as Partial<AgentConfig>);
  };

  if (isLoading) {
    return (
      <div>
        <div className="h-7 w-40 bg-slate-200 dark:bg-slate-700 rounded animate-pulse mb-6" />
        <div className="card h-64 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="max-w-xl">
      <div className="mb-6">
        <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">AI Provider</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Configure which LLM powers the alert investigation agent.
        </p>
      </div>

      <div className="card space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Provider</label>
          <select className="input" value={form.AI_PROVIDER} onChange={(e) => handleProviderChange(e.target.value)}>
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Model name</label>
          <input
            className="input"
            value={form.OPENAI_MODEL}
            onChange={(e) => setForm((f) => ({ ...f, OPENAI_MODEL: e.target.value }))}
            placeholder="e.g. gpt-4o"
            disabled={form.AI_PROVIDER === "fake"}
          />
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
            pydantic-ai model string prefix is applied automatically based on provider.
          </p>
        </div>

        {form.AI_PROVIDER !== "fake" && (
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              API Key
              {data?.OPENAI_API_KEY === "***" && <span className="ml-2 badge-green">set</span>}
            </label>
            <div className="relative">
              <input
                className="input pr-10"
                type={showKey ? "text" : "password"}
                value={form.OPENAI_API_KEY}
                onChange={(e) => setForm((f) => ({ ...f, OPENAI_API_KEY: e.target.value }))}
                placeholder={data?.OPENAI_API_KEY === "***" ? "Leave blank to keep existing key" : "sk-…"}
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
              >
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="button"
            role="switch"
            aria-checked={form.LLM_ENABLED}
            onClick={() => setForm((f) => ({ ...f, LLM_ENABLED: !f.LLM_ENABLED }))}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${form.LLM_ENABLED ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
          >
            <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${form.LLM_ENABLED ? "translate-x-4" : "translate-x-1"}`} />
          </button>
          <span className="text-sm text-slate-700 dark:text-slate-300">Enable LLM investigations</span>
        </div>

        <div className="flex items-center gap-3 pt-2 border-t border-slate-100 dark:border-slate-700">
          <button className="btn-primary" onClick={handleSave} disabled={mutation.isPending}>
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
