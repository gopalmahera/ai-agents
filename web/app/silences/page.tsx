"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SilenceRule, SilencesConfig } from "@/lib/types";
import {
  buildSilencesConfig,
  silenceToConditions,
  validateSilencesConfig,
  type EditableSilence,
  type SilencesValidation,
} from "@/lib/silences-validation";
import type { LabelCondition } from "@/lib/routing-validation";
import { toSilencesYaml } from "@/lib/silences-yaml";
import {
  Plus,
  Trash2,
  Save,
  CheckCircle,
  AlertCircle,
  Copy,
  FileCode2,
  BellOff,
  Archive,
} from "lucide-react";

const COMMON_LABELS = ["severity", "stage", "namespace", "alertname", "cluster", "job"];
type Tab = "active" | "disabled";

function newSilence(): EditableSilence {
  return {
    id: crypto.randomUUID(),
    comment: "",
    mode: "permanent",
    ends_at: "",
    conditions: [{ key: "", kind: "exact", value: "" }],
  };
}

function ConditionRows({
  conditions,
  onChange,
  errors,
}: {
  conditions: LabelCondition[];
  onChange: (c: LabelCondition[]) => void;
  errors?: Record<number, string>;
}) {
  return (
    <div className="space-y-2">
      {conditions.map((condition, i) => (
        <div key={i}>
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="input text-sm flex-1 min-w-[7rem]"
              list="silence-label-keys"
              value={condition.key}
              onChange={(e) =>
                onChange(conditions.map((x, j) => (j === i ? { ...x, key: e.target.value } : x)))
              }
              placeholder="label key"
            />
            <select
              className="input text-sm w-36"
              value={condition.kind}
              onChange={(e) =>
                onChange(
                  conditions.map((x, j) =>
                    j === i ? { ...x, kind: e.target.value as LabelCondition["kind"] } : x,
                  ),
                )
              }
            >
              <option value="exact">equals</option>
              <option value="regex">matches regex</option>
            </select>
            <input
              className="input text-sm flex-[2] min-w-[10rem] font-mono"
              value={condition.value}
              onChange={(e) =>
                onChange(conditions.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))
              }
              placeholder="value"
            />
            <button
              type="button"
              className="btn-ghost p-2 text-red-500"
              disabled={conditions.length <= 1}
              onClick={() => onChange(conditions.filter((_, j) => j !== i))}
            >
              <Trash2 size={14} />
            </button>
          </div>
          {errors?.[i] && <p className="text-xs text-red-600 mt-1">{errors[i]}</p>}
        </div>
      ))}
      <button
        type="button"
        className="btn-ghost text-xs px-2 py-1"
        onClick={() => onChange([...conditions, { key: "", kind: "exact", value: "" }])}
      >
        <Plus size={12} /> Add matcher
      </button>
    </div>
  );
}

function YamlPreview({ yaml, saved }: { yaml: string; saved: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className={`card sticky top-4 ${saved ? "border-emerald-300 dark:border-emerald-800" : ""}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <FileCode2 size={16} className="text-indigo-500" />
          <div>
            <h2 className="text-sm font-semibold">silences.yaml</h2>
            <p className="text-xs text-slate-400">{saved ? "Saved" : "Live preview"}</p>
          </div>
        </div>
        <button
          type="button"
          className="btn-secondary text-xs px-2.5 py-1.5"
          onClick={async () => {
            await navigator.clipboard.writeText(yaml);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
        >
          <Copy size={12} /> {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="text-xs font-mono bg-slate-950/5 dark:bg-slate-950/40 rounded-lg p-3 overflow-auto max-h-[calc(100vh-10rem)] whitespace-pre-wrap">
        {yaml}
      </pre>
    </div>
  );
}

export default function SilencesPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("active");
  const [activeSilences, setActiveSilences] = useState<EditableSilence[]>([]);
  const [disabledSilences, setDisabledSilences] = useState<SilenceRule[]>([]);
  const [validation, setValidation] = useState<SilencesValidation | null>(null);
  const [saved, setSaved] = useState(false);
  const [enableId, setEnableId] = useState<string | null>(null);
  const [enableMode, setEnableMode] = useState<"permanent" | "until">("until");
  const [enableEndsAt, setEnableEndsAt] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["silences"],
    queryFn: () => api.get<SilencesConfig>("/api/config/mute"),
  });

  useEffect(() => {
    if (!data) return;
    setActiveSilences(
      (data.silences?.active ?? []).map((s) => ({
        id: s.id,
        comment: s.comment ?? "",
        mode: s.mode ?? "permanent",
        ends_at: s.ends_at ?? "",
        conditions: silenceToConditions(s),
      })),
    );
    setDisabledSilences(data.silences?.disabled ?? []);
    setValidation(null);
  }, [data]);

  const silencesConfig = useMemo(
    () => buildSilencesConfig(activeSilences, disabledSilences),
    [activeSilences, disabledSilences],
  );
  const yamlPreview = useMemo(() => toSilencesYaml(silencesConfig), [silencesConfig]);

  const saveMutation = useMutation({
    mutationFn: () => api.post("/api/config/mute", silencesConfig),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["silences"] });
      setValidation(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const disableMutation = useMutation({
    mutationFn: (id: string) => api.post(`/api/config/mute/silences/${id}/disable`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["silences"] }),
  });

  const enableMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.post(`/api/config/mute/silences/${id}/enable`, body),
    onSuccess: () => {
      setEnableId(null);
      qc.invalidateQueries({ queryKey: ["silences"] });
    },
  });

  const handleSave = () => {
    const result = validateSilencesConfig(activeSilences);
    setValidation(result);
    if (!result.valid) return;
    saveMutation.mutate();
  };

  if (isLoading) return <div className="card h-64 animate-pulse" />;

  return (
    <div className="max-w-6xl">
      <datalist id="silence-label-keys">
        {COMMON_LABELS.map((l) => (
          <option key={l} value={l} />
        ))}
      </datalist>

      <div className="mb-6">
        <h1 className="text-xl font-[Poppins] font-semibold">Silences</h1>
        <p className="text-sm text-slate-500 mt-1">
          Suppress LLM investigation and Slack RCA for matching alerts (Alertmanager-style).
        </p>
      </div>

      <div className="flex gap-2 mb-4">
        {(
          [
            ["active", "Active Silences", BellOff],
            ["disabled", "Disabled", Archive],
          ] as const
        ).map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            className={`btn-secondary text-xs ${tab === key ? "ring-2 ring-primary/40" : ""}`}
            onClick={() => setTab(key)}
          >
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_26rem] gap-6 items-start">
        <div className="min-w-0 space-y-4">
          {tab === "active" && (
            <>
              {activeSilences.map((silence, idx) => (
                <div key={silence.id} className="card space-y-3">
                  <div className="flex justify-between items-start gap-2">
                    <input
                      className="input flex-1"
                      value={silence.comment}
                      onChange={(e) =>
                        setActiveSilences((rows) =>
                          rows.map((r, i) => (i === idx ? { ...r, comment: e.target.value } : r)),
                        )
                      }
                      placeholder="Comment (e.g. Kafka maintenance)"
                    />
                    <button
                      type="button"
                      className="btn-ghost p-2 text-red-500"
                      onClick={() => disableMutation.mutate(silence.id)}
                    >
                      Disable
                    </button>
                  </div>
                  {validation?.silences[silence.id]?.general && (
                    <p className="text-xs text-red-600">{validation.silences[silence.id].general}</p>
                  )}
                  <ConditionRows
                    conditions={silence.conditions}
                    errors={validation?.silences[silence.id]?.conditions}
                    onChange={(conditions) =>
                      setActiveSilences((rows) =>
                        rows.map((r, i) => (i === idx ? { ...r, conditions } : r)),
                      )
                    }
                  />
                  <select
                    className="input text-sm"
                    value={silence.mode}
                    onChange={(e) =>
                      setActiveSilences((rows) =>
                        rows.map((r, i) =>
                          i === idx ? { ...r, mode: e.target.value as EditableSilence["mode"] } : r,
                        ),
                      )
                    }
                  >
                    <option value="permanent">Permanent (until manually disabled)</option>
                    <option value="until">Until end date/time</option>
                  </select>
                  {silence.mode === "until" && (
                    <input
                      type="datetime-local"
                      className="input text-sm"
                      value={silence.ends_at ? silence.ends_at.slice(0, 16) : ""}
                      onChange={(e) =>
                        setActiveSilences((rows) =>
                          rows.map((r, i) =>
                            i === idx
                              ? { ...r, ends_at: e.target.value ? `${e.target.value}:00Z` : "" }
                              : r,
                          ),
                        )
                      }
                    />
                  )}
                  <button
                    type="button"
                    className="btn-ghost text-xs text-red-500"
                    onClick={() => setActiveSilences((rows) => rows.filter((r) => r.id !== silence.id))}
                  >
                    <Trash2 size={12} /> Remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setActiveSilences((r) => [...r, newSilence()])}
              >
                <Plus size={14} /> Add silence
              </button>
            </>
          )}

          {tab === "disabled" && (
            <>
              {disabledSilences.length === 0 && (
                <p className="text-sm text-slate-400 text-center py-8">No disabled silences.</p>
              )}
              {disabledSilences.map((silence) => (
                <div key={silence.id} className="card space-y-2">
                  <div className="flex justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium">{silence.comment || silence.id}</p>
                      <p className="text-xs text-slate-400">
                        {silence.disabled_reason ?? "disabled"} · {silence.disabled_at ?? ""}
                      </p>
                      <p className="text-xs font-mono text-slate-500 mt-1">
                        mode={silence.mode}
                        {silence.ends_at ? ` · ends ${silence.ends_at}` : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn-secondary text-xs"
                      onClick={() => {
                        setEnableId(silence.id);
                        setEnableMode(silence.mode ?? "permanent");
                        setEnableEndsAt(silence.ends_at ?? "");
                      }}
                    >
                      Re-enable
                    </button>
                  </div>
                </div>
              ))}
              {enableId && (
                <div className="card border-indigo-200 space-y-2">
                  <p className="text-sm font-medium">Re-enable silence</p>
                  <select
                    className="input text-sm"
                    value={enableMode}
                    onChange={(e) => setEnableMode(e.target.value as typeof enableMode)}
                  >
                    <option value="permanent">Permanent</option>
                    <option value="until">Until date</option>
                  </select>
                  {enableMode === "until" && (
                    <input
                      type="datetime-local"
                      className="input text-sm"
                      value={enableEndsAt ? enableEndsAt.slice(0, 16) : ""}
                      onChange={(e) =>
                        setEnableEndsAt(e.target.value ? `${e.target.value}:00Z` : "")
                      }
                    />
                  )}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="btn-primary text-xs"
                      onClick={() =>
                        enableMutation.mutate({
                          id: enableId,
                          body: {
                            mode: enableMode,
                            ...(enableMode === "until" ? { ends_at: enableEndsAt } : {}),
                          },
                        })
                      }
                    >
                      Confirm
                    </button>
                    <button type="button" className="btn-secondary text-xs" onClick={() => setEnableId(null)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {validation && !validation.valid && (
            <div className="card border-red-200 bg-red-50 dark:bg-red-950/20">
              <div className="flex gap-2">
                <AlertCircle size={16} className="text-red-500 shrink-0" />
                <ul className="text-xs text-red-700 list-disc list-inside">
                  {validation.global.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {tab === "active" && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="btn-primary"
                onClick={handleSave}
                disabled={saveMutation.isPending}
              >
                <Save size={14} /> {saveMutation.isPending ? "Saving…" : "Save"}
              </button>
              {saved && (
                <span className="text-sm text-emerald-600 flex items-center gap-1">
                  <CheckCircle size={14} /> Saved
                </span>
              )}
              {saveMutation.isError && (
                <span className="text-sm text-red-600">{(saveMutation.error as Error).message}</span>
              )}
            </div>
          )}
        </div>

        <aside>
          <YamlPreview yaml={yamlPreview} saved={saved} />
        </aside>
      </div>
    </div>
  );
}
