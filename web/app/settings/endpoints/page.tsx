"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { Plus, Trash2, Save, CheckCircle, Server } from "lucide-react";
import { api } from "@/lib/api";
import type { EndpointsConfig, EndpointType } from "@/lib/types";
import {
  ENDPOINT_TYPES,
  blankEndpoint,
  fromEndpointsConfig,
  toEndpointsConfig,
  validateEndpoints,
  type EditableEndpoint,
} from "@/lib/endpoints-validation";

const TYPE_LABEL: Record<EndpointType, string> = {
  prometheus: "Prometheus",
  loki: "Loki",
  kubernetes: "Kubernetes",
  aws: "AWS (Cloud)",
};

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{hint}</p>}
    </div>
  );
}

function AuthFields({ ep, patch }: { ep: EditableEndpoint; patch: (p: Partial<EditableEndpoint>) => void }) {
  if (ep.type === "prometheus" || ep.type === "loki") {
    return (
      <>
        <Field label="URL" hint="Direct API endpoint (http/https).">
          <input className="input" value={ep.url} placeholder="http://prometheus.internal:9090"
            onChange={(e) => patch({ url: e.target.value })} />
        </Field>
        <Field label="Auth">
          <select className="input" value={ep.http_auth_mode} onChange={(e) => patch({ http_auth_mode: e.target.value })}>
            <option value="none">None</option>
            <option value="basic">Basic</option>
            <option value="bearer">Bearer token</option>
          </select>
        </Field>
        {ep.http_auth_mode === "basic" && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Username">
              <input className="input" value={ep.username} onChange={(e) => patch({ username: e.target.value })} />
            </Field>
            <Field label="Password">
              <input className="input" type="password" value={ep.password}
                placeholder="Leave *** to keep existing"
                onChange={(e) => patch({ password: e.target.value })} />
            </Field>
          </div>
        )}
        {ep.http_auth_mode === "bearer" && (
          <Field label="Token">
            <input className="input" type="password" value={ep.bearer_token}
              placeholder="Leave *** to keep existing"
              onChange={(e) => patch({ bearer_token: e.target.value })} />
          </Field>
        )}
      </>
    );
  }
  if (ep.type === "kubernetes") {
    return (
      <>
        <Field label="Kube-context" hint="A context in the mounted multi-cluster kubeconfig. Leave all fields empty for in-cluster.">
          <input className="input" value={ep.kube_context} placeholder="prod-ap-south-1"
            onChange={(e) => patch({ kube_context: e.target.value })} />
        </Field>
        <p className="text-xs text-slate-400 dark:text-slate-500">— or — connect explicitly:</p>
        <Field label="API server">
          <input className="input" value={ep.api_server} placeholder="https://k8s.prod.example.com"
            onChange={(e) => patch({ api_server: e.target.value })} />
        </Field>
        <Field label="Bearer token">
          <input className="input" type="password" value={ep.kube_token}
            placeholder="Leave *** to keep existing"
            onChange={(e) => patch({ kube_token: e.target.value })} />
        </Field>
        <Field label="CA certificate (PEM)" hint="Optional. Empty disables TLS verification.">
          <textarea className="input font-mono text-xs" rows={3} value={ep.ca_cert}
            placeholder="-----BEGIN CERTIFICATE-----"
            onChange={(e) => patch({ ca_cert: e.target.value })} />
        </Field>
      </>
    );
  }
  // aws
  return (
    <>
      <Field label="Region">
        <input className="input" value={ep.region} placeholder="ap-south-1"
          onChange={(e) => patch({ region: e.target.value })} />
      </Field>
      <Field label="Auth" hint="Default = the agent's own IAM role (IRSA).">
        <select className="input" value={ep.aws_auth_mode} onChange={(e) => patch({ aws_auth_mode: e.target.value })}>
          <option value="default">Default (IRSA / pod role)</option>
          <option value="assume_role">Assume role</option>
          <option value="keys">Access keys</option>
        </select>
      </Field>
      {ep.aws_auth_mode === "assume_role" && (
        <Field label="Role ARN">
          <input className="input" value={ep.role_arn} placeholder="arn:aws:iam::123456789012:role/cloudwatch-read"
            onChange={(e) => patch({ role_arn: e.target.value })} />
        </Field>
      )}
      {ep.aws_auth_mode === "keys" && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Access key ID">
            <input className="input" value={ep.access_key_id} onChange={(e) => patch({ access_key_id: e.target.value })} />
          </Field>
          <Field label="Secret access key">
            <input className="input" type="password" value={ep.secret_access_key}
              placeholder="Leave *** to keep existing"
              onChange={(e) => patch({ secret_access_key: e.target.value })} />
          </Field>
        </div>
      )}
    </>
  );
}

export default function EndpointsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["endpoints"],
    queryFn: () => api.get<EndpointsConfig>("/api/config/endpoints"),
  });

  const [eps, setEps] = useState<EditableEndpoint[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setEps(fromEndpointsConfig(data));
  }, [data]);

  const validation = validateEndpoints(eps);

  const mutation = useMutation({
    mutationFn: () => api.post<{ status: string }>("/api/config/endpoints", toEndpointsConfig(eps)),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      qc.invalidateQueries({ queryKey: ["endpoints"] });
    },
  });

  const patch = (id: string, p: Partial<EditableEndpoint>) =>
    setEps((prev) => prev.map((e) => (e.id === id ? { ...e, ...p } : e)));
  const remove = (id: string) => setEps((prev) => prev.filter((e) => e.id !== id));
  const add = (type: EndpointType) =>
    setEps((prev) => [...prev, blankEndpoint(type, `ep-new-${Date.now()}-${prev.length}`)]);

  if (isLoading) return <div className="card h-64 animate-pulse" />;

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">Endpoint Management</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Reusable data-source endpoints with auth. Environments select these by name.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-5">
        {ENDPOINT_TYPES.map((t) => (
          <button key={t.value} className="btn-secondary" onClick={() => add(t.value)}>
            <Plus size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {eps.length === 0 && (
          <div className="card text-sm text-slate-500 dark:text-slate-400 flex items-center gap-2">
            <Server size={15} /> No endpoints yet — add one above.
          </div>
        )}
        {eps.map((ep) => (
          <div key={ep.id} className="card space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 grid grid-cols-2 gap-3">
                <Field label="Name">
                  <input className="input" value={ep.name} placeholder="prod-prometheus"
                    onChange={(e) => patch(ep.id, { name: e.target.value })} />
                </Field>
                <Field label="Type">
                  <input className="input bg-slate-50 dark:bg-slate-900" value={TYPE_LABEL[ep.type]} disabled />
                </Field>
              </div>
              <button className="btn-ghost text-red-500 mt-6" onClick={() => remove(ep.id)} aria-label="Remove endpoint">
                <Trash2 size={15} />
              </button>
            </div>
            <AuthFields ep={ep} patch={(p) => patch(ep.id, p)} />
            {validation.eps[ep.id] && (
              <p className="text-sm text-red-600 dark:text-red-400">{validation.eps[ep.id]}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 mt-6">
        <button className="btn-primary" onClick={() => mutation.mutate()} disabled={!validation.valid || mutation.isPending}>
          <Save size={15} /> {mutation.isPending ? "Saving…" : "Save endpoints"}
        </button>
        {saved && (
          <span className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
            <CheckCircle size={15} /> Saved
          </span>
        )}
        {mutation.error && <span className="text-sm text-red-600 dark:text-red-400">{(mutation.error as Error).message}</span>}
      </div>
    </div>
  );
}
