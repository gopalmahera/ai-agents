"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AgentConfig } from "@/lib/types";
import { useState, useEffect } from "react";
import { Save, Eye, EyeOff, CheckCircle, ShieldCheck } from "lucide-react";

const PROVIDERS = [
  { value: "openai", label: "OpenAI", defaultModel: "gpt-4o" },
  { value: "anthropic", label: "Anthropic", defaultModel: "claude-sonnet-5" },
  { value: "gemini", label: "Google Gemini (Vertex)", defaultModel: "gemini-2.0-flash" },
  { value: "bedrock", label: "AWS Bedrock", defaultModel: "us.anthropic.claude-sonnet-4-5" },
  { value: "fake", label: "Fake (echo)", defaultModel: "echo" },
];

// Fields posted per provider (text = dirty-diffed, secret = posted only when re-entered)
const FIELDS: Record<string, { text: string[]; secret: string[] }> = {
  openai: { text: ["OPENAI_MODEL", "OPENAI_BASE_URL"], secret: ["OPENAI_API_KEY"] },
  anthropic: { text: ["OPENAI_MODEL"], secret: ["ANTHROPIC_API_KEY"] },
  gemini: {
    text: ["OPENAI_MODEL", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_GENAI_USE_VERTEXAI"],
    secret: ["GOOGLE_SA_JSON", "GEMINI_API_KEY"],
  },
  bedrock: { text: ["OPENAI_MODEL", "AWS_REGION", "AWS_ROLE_ARN"], secret: [] },
  fake: { text: [], secret: [] },
};

const BLANK = {
  AI_PROVIDER: "openai",
  OPENAI_MODEL: "gpt-4o",
  OPENAI_API_KEY: "",
  OPENAI_BASE_URL: "",
  ANTHROPIC_API_KEY: "",
  GEMINI_API_KEY: "",
  GOOGLE_SA_JSON: "",
  GOOGLE_CLOUD_PROJECT: "",
  GOOGLE_CLOUD_LOCATION: "us-central1",
  GOOGLE_GENAI_USE_VERTEXAI: "true",
  AWS_REGION: "",
  AWS_ROLE_ARN: "",
  LLM_ENABLED: true,
};

type Form = typeof BLANK;

export default function AIConfigPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.get<AgentConfig>("/api/config"),
  });

  const [form, setForm] = useState<Form>(BLANK);
  const [showSecret, setShowSecret] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!data) return;
    const isSet = (v: unknown) => v === "***"; // secrets arrive masked
    setForm({
      AI_PROVIDER: data.AI_PROVIDER ?? "openai",
      OPENAI_MODEL: data.OPENAI_MODEL ?? "gpt-4o",
      OPENAI_API_KEY: "",
      OPENAI_BASE_URL: data.OPENAI_BASE_URL ?? "",
      ANTHROPIC_API_KEY: "",
      GEMINI_API_KEY: "",
      GOOGLE_SA_JSON: "",
      GOOGLE_CLOUD_PROJECT: data.GOOGLE_CLOUD_PROJECT ?? "",
      GOOGLE_CLOUD_LOCATION: data.GOOGLE_CLOUD_LOCATION ?? "us-central1",
      GOOGLE_GENAI_USE_VERTEXAI: String(data.GOOGLE_GENAI_USE_VERTEXAI ?? "true"),
      AWS_REGION: data.AWS_REGION ?? "",
      AWS_ROLE_ARN: data.AWS_ROLE_ARN ?? "",
      LLM_ENABLED: data.LLM_ENABLED === true || data.LLM_ENABLED === "true",
    });
    void isSet;
  }, [data]);

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/api/config", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const set = (k: keyof Form, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  const handleProviderChange = (provider: string) => {
    const p = PROVIDERS.find((p) => p.value === provider);
    setForm((f) => ({ ...f, AI_PROVIDER: provider, OPENAI_MODEL: p?.defaultModel ?? f.OPENAI_MODEL }));
  };

  const handleSave = () => {
    const fields = FIELDS[form.AI_PROVIDER] ?? { text: [], secret: [] };
    const payload: Record<string, unknown> = {};
    if (form.AI_PROVIDER !== (data?.AI_PROVIDER ?? "")) payload.AI_PROVIDER = form.AI_PROVIDER;
    fields.text.forEach((k) => {
      const cur = String(form[k as keyof Form] ?? "");
      if (cur !== String((data as unknown as Record<string, unknown>)?.[k] ?? "")) payload[k] = cur;
    });
    fields.secret.forEach((k) => {
      const v = String(form[k as keyof Form] ?? "");
      if (v) payload[k] = v; // only when re-entered
    });
    const dataLlm = data?.LLM_ENABLED === true || data?.LLM_ENABLED === "true";
    if (form.LLM_ENABLED !== dataLlm) payload.LLM_ENABLED = form.LLM_ENABLED;
    mutation.mutate(payload);
  };

  const provider = form.AI_PROVIDER;
  const secretIsSet = (key: keyof AgentConfig) => (data?.[key] as unknown) === "***";

  if (isLoading) {
    return (
      <div>
        <div className="h-7 w-40 bg-slate-200 dark:bg-slate-700 rounded animate-pulse mb-6" />
        <div className="card h-64 animate-pulse" />
      </div>
    );
  }

  const labelCls = "block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5";
  const hintCls = "text-xs text-slate-400 dark:text-slate-500 mt-1";

  const SecretField = ({ field, label, placeholder, textarea }: {
    field: keyof Form; label: string; placeholder: string; textarea?: boolean;
  }) => (
    <div>
      <label className={labelCls}>
        {label}
        {secretIsSet(field as keyof AgentConfig) && <span className="ml-2 badge-green">set</span>}
      </label>
      <div className="relative">
        {textarea ? (
          <textarea
            className="input font-mono text-xs min-h-[120px]"
            value={String(form[field] ?? "")}
            onChange={(e) => set(field, e.target.value)}
            placeholder={secretIsSet(field as keyof AgentConfig) ? "Leave blank to keep existing" : placeholder}
          />
        ) : (
          <>
            <input
              className="input pr-10"
              type={showSecret ? "text" : "password"}
              value={String(form[field] ?? "")}
              onChange={(e) => set(field, e.target.value)}
              placeholder={secretIsSet(field as keyof AgentConfig) ? "Leave blank to keep existing key" : placeholder}
            />
            <button
              type="button"
              onClick={() => setShowSecret((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
            >
              {showSecret ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </>
        )}
      </div>
    </div>
  );

  const TextField = ({ field, label, placeholder, hint }: {
    field: keyof Form; label: string; placeholder?: string; hint?: string;
  }) => (
    <div>
      <label className={labelCls}>{label}</label>
      <input
        className="input"
        value={String(form[field] ?? "")}
        onChange={(e) => set(field, e.target.value)}
        placeholder={placeholder}
      />
      {hint && <p className={hintCls}>{hint}</p>}
    </div>
  );

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
          <label className={labelCls}>Provider</label>
          <select className="input" value={provider} onChange={(e) => handleProviderChange(e.target.value)}>
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        {provider !== "fake" && (
          <TextField field="OPENAI_MODEL" label="Model name" hint="Model id for the selected provider." />
        )}

        {/* ── OpenAI ── */}
        {provider === "openai" && (
          <>
            <SecretField field="OPENAI_API_KEY" label="API Key" placeholder="sk-…" />
            <TextField
              field="OPENAI_BASE_URL"
              label="Base URL (optional)"
              placeholder="https://your-resource.openai.azure.com/…"
              hint="Set for Azure OpenAI or a proxy. Leave blank for api.openai.com."
            />
          </>
        )}

        {/* ── Anthropic ── */}
        {provider === "anthropic" && (
          <SecretField field="ANTHROPIC_API_KEY" label="API Key" placeholder="sk-ant-…" />
        )}

        {/* ── Gemini (Vertex) ── */}
        {provider === "gemini" && (
          <>
            <div className="flex items-center gap-3">
              <button
                type="button"
                role="switch"
                aria-checked={form.GOOGLE_GENAI_USE_VERTEXAI === "true"}
                onClick={() => set("GOOGLE_GENAI_USE_VERTEXAI", form.GOOGLE_GENAI_USE_VERTEXAI === "true" ? "false" : "true")}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${form.GOOGLE_GENAI_USE_VERTEXAI === "true" ? "bg-primary" : "bg-slate-300 dark:bg-slate-600"}`}
              >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${form.GOOGLE_GENAI_USE_VERTEXAI === "true" ? "translate-x-4" : "translate-x-1"}`} />
              </button>
              <span className="text-sm text-slate-700 dark:text-slate-300">Use Vertex AI (service-account JSON)</span>
            </div>
            {form.GOOGLE_GENAI_USE_VERTEXAI === "true" ? (
              <>
                <TextField field="GOOGLE_CLOUD_PROJECT" label="GCP Project ID" placeholder="my-gcp-project" />
                <TextField field="GOOGLE_CLOUD_LOCATION" label="Location / Region" placeholder="us-central1" />
                <SecretField field="GOOGLE_SA_JSON" label="Service Account JSON" placeholder='{ "type": "service_account", … }' textarea />
              </>
            ) : (
              <SecretField field="GEMINI_API_KEY" label="Gemini API Key (GLA mode)" placeholder="AIza…" />
            )}
          </>
        )}

        {/* ── Bedrock (IRSA) ── */}
        {provider === "bedrock" && (
          <>
            <TextField field="AWS_REGION" label="AWS Region" placeholder="ap-south-1" />
            <TextField
              field="AWS_ROLE_ARN"
              label="Assume Role ARN (optional)"
              placeholder="arn:aws:iam::123456789012:role/bedrock-invoke"
              hint="Leave blank to use the pod's IAM role directly."
            />
            <div className="flex items-start gap-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-3">
              <ShieldCheck size={16} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-800 dark:text-amber-300">
                Auth uses the pod&apos;s IAM role (IRSA) — no key is stored here. Annotate the ServiceAccount with{" "}
                <code className="font-mono">eks.amazonaws.com/role-arn</code> and grant it{" "}
                <code className="font-mono">bedrock:InvokeModel</code>.
              </p>
            </div>
          </>
        )}

        <div className="flex items-center gap-3">
          <button
            type="button"
            role="switch"
            aria-checked={form.LLM_ENABLED}
            onClick={() => set("LLM_ENABLED", !form.LLM_ENABLED)}
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
