"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Save, CheckCircle, Server } from "lucide-react";
import { api } from "@/lib/api";
import type { Endpoint, EndpointType } from "@/lib/types";
import {
  ENDPOINT_TYPES,
  blankEndpoint,
  fromEndpointsConfig,
  toEndpointsConfig,
  validateEndpoints,
  type EditableEndpoint,
} from "@/lib/endpoints-validation";
import { SettingsPageLayout } from "@/components/settings/SettingsPageLayout";
import { SettingsToolbar } from "@/components/settings/SettingsToolbar";
import { SettingsCardGrid } from "@/components/settings/SettingsCardGrid";
import { SettingsEntityCard } from "@/components/settings/SettingsEntityCard";
import { SettingsDrawer } from "@/components/settings/SettingsDrawer";

const TYPE_LABEL: Record<EndpointType, string> = {
  prometheus: "Prometheus",
  loki: "Loki",
  kubernetes: "Kubernetes",
  aws: "AWS",
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
        <Field label="URL">
          <input className="input" value={ep.url} onChange={(e) => patch({ url: e.target.value })} />
        </Field>
        <Field label="Auth">
          <select className="input" value={ep.http_auth_mode} onChange={(e) => patch({ http_auth_mode: e.target.value })}>
            <option value="none">None</option>
            <option value="basic">Basic</option>
            <option value="bearer">Bearer</option>
          </select>
        </Field>
        {ep.http_auth_mode === "basic" && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Username">
              <input className="input" value={ep.username} onChange={(e) => patch({ username: e.target.value })} />
            </Field>
            <Field label="Password">
              <input className="input" type="password" value={ep.password} placeholder="Leave *** to keep"
                onChange={(e) => patch({ password: e.target.value })} />
            </Field>
          </div>
        )}
        {ep.http_auth_mode === "bearer" && (
          <Field label="Token">
            <input className="input" type="password" value={ep.bearer_token} placeholder="Leave *** to keep"
              onChange={(e) => patch({ bearer_token: e.target.value })} />
          </Field>
        )}
      </>
    );
  }
  if (ep.type === "kubernetes") {
    return (
      <>
        <Field label="Kube-context">
          <input className="input" value={ep.kube_context} onChange={(e) => patch({ kube_context: e.target.value })} />
        </Field>
        <Field label="API server">
          <input className="input" value={ep.api_server} onChange={(e) => patch({ api_server: e.target.value })} />
        </Field>
        <Field label="Bearer token">
          <input className="input" type="password" value={ep.kube_token} placeholder="Leave *** to keep"
            onChange={(e) => patch({ kube_token: e.target.value })} />
        </Field>
      </>
    );
  }
  return (
    <>
      <Field label="Region">
        <input className="input" value={ep.region} onChange={(e) => patch({ region: e.target.value })} />
      </Field>
      <Field label="Auth">
        <select className="input" value={ep.aws_auth_mode} onChange={(e) => patch({ aws_auth_mode: e.target.value })}>
          <option value="default">Default (IRSA)</option>
          <option value="assume_role">Assume role</option>
          <option value="keys">Access keys</option>
        </select>
      </Field>
      {ep.aws_auth_mode === "assume_role" && (
        <Field label="Role ARN">
          <input className="input" value={ep.role_arn} onChange={(e) => patch({ role_arn: e.target.value })} />
        </Field>
      )}
      {ep.aws_auth_mode === "keys" && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Access key ID">
            <input className="input" value={ep.access_key_id} onChange={(e) => patch({ access_key_id: e.target.value })} />
          </Field>
          <Field label="Secret access key">
            <input className="input" type="password" value={ep.secret_access_key} placeholder="Leave *** to keep"
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
    queryFn: () => api.get<{ endpoints: Endpoint[] }>("/api/config/endpoints"),
  });

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<EditableEndpoint | null>(null);
  const [originalName, setOriginalName] = useState<string | undefined>();
  const [saved, setSaved] = useState(false);

  const eps = useMemo(() => fromEndpointsConfig(data), [data]);

  const filtered = useMemo(() => {
    return eps.filter((e) => {
      if (typeFilter && e.type !== typeFilter) return false;
      if (!search) return true;
      const q = search.toLowerCase();
      return e.name.toLowerCase().includes(q) || e.url.toLowerCase().includes(q) || e.region.toLowerCase().includes(q);
    });
  }, [eps, search, typeFilter]);

  const validation = editing ? validateEndpoints([editing]) : { valid: true, eps: {} as Record<string, string> };

  const saveMutation = useMutation({
    mutationFn: async ({ ep, originalName }: { ep: EditableEndpoint; originalName?: string }) => {
      const payload = toEndpointsConfig([ep]).endpoints[0];
      if (originalName) {
        await api.put(`/api/v1/settings/endpoints/${encodeURIComponent(originalName)}`, payload);
      } else {
        await api.post("/api/v1/settings/endpoints", payload);
      }
    },
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      setDrawerOpen(false);
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["endpoints"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.delete(`/api/v1/settings/endpoints/${encodeURIComponent(name)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["endpoints"] }),
  });

  const openNew = (type: EndpointType) => {
    setOriginalName(undefined);
    setEditing(blankEndpoint(type, `new-${Date.now()}`));
    setDrawerOpen(true);
  };

  const openEdit = (ep: EditableEndpoint) => {
    setOriginalName(ep.name.trim() || undefined);
    setEditing({ ...ep });
    setDrawerOpen(true);
  };

  if (isLoading) return <div className="card h-64 animate-pulse" />;

  return (
    <SettingsPageLayout
      title="Endpoint Management"
      description="Reusable data-source endpoints with auth. Environments select these by name."
      toolbar={
        <SettingsToolbar
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search endpoints…"
          filter={typeFilter}
          filterOptions={[{ value: "", label: "All types" }, ...ENDPOINT_TYPES.map((t) => ({ value: t.value, label: t.label }))]}
          onFilterChange={setTypeFilter}
          addLabel="Add endpoint"
          onAdd={() => openNew("prometheus")}
          extra={
            <div className="flex gap-1 flex-wrap">
              {ENDPOINT_TYPES.map((t) => (
                <button key={t.value} className="btn-secondary text-xs" onClick={() => openNew(t.value)}>
                  + {t.label}
                </button>
              ))}
            </div>
          }
        />
      }
    >
      {filtered.length === 0 ? (
        <div className="card text-sm text-slate-500 flex items-center gap-2">
          <Server size={15} /> No endpoints match — add one above.
        </div>
      ) : (
        <SettingsCardGrid>
          {filtered.map((ep) => (
            <SettingsEntityCard
              key={ep.id}
              title={ep.name || "(unnamed)"}
              subtitle={ep.type === "aws" ? ep.region || "AWS" : ep.url || TYPE_LABEL[ep.type]}
              badges={<span className="badge-green text-xs">{TYPE_LABEL[ep.type]}</span>}
              onClick={() => openEdit(ep)}
              onDelete={ep.name ? () => deleteMutation.mutate(ep.name.trim()) : undefined}
            />
          ))}
        </SettingsCardGrid>
      )}

      <SettingsDrawer
        open={drawerOpen && !!editing}
        title={editing?.name ? `Edit ${editing.name}` : "New endpoint"}
        onClose={() => { setDrawerOpen(false); setEditing(null); }}
        footer={
          <>
            <button className="btn-primary" disabled={!validation.valid || saveMutation.isPending}
              onClick={() => editing && saveMutation.mutate({ ep: editing, originalName })}>
              <Save size={15} /> {saveMutation.isPending ? "Saving…" : "Save"}
            </button>
            {saved && (
              <span className="flex items-center gap-1 text-sm text-emerald-600">
                <CheckCircle size={15} /> Saved
              </span>
            )}
            {saveMutation.error && (
              <span className="text-sm text-red-600">{(saveMutation.error as Error).message}</span>
            )}
          </>
        }
      >
        {editing && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Name">
                <input className="input" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              </Field>
              <Field label="Type">
                <input className="input bg-slate-50 dark:bg-slate-900" value={TYPE_LABEL[editing.type]} disabled />
              </Field>
            </div>
            <AuthFields ep={editing} patch={(p) => setEditing({ ...editing, ...p })} />
            {validation.eps[editing.id] && (
              <p className="text-sm text-red-600">{validation.eps[editing.id]}</p>
            )}
          </>
        )}
      </SettingsDrawer>
    </SettingsPageLayout>
  );
}
