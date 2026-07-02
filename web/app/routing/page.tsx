"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RoutingConfig, RoutingRule, TimeIntervalsConfig } from "@/lib/types";
import {
  type EditableRule,
  type LabelCondition,
  type RoutingValidation,
  validateRouting,
} from "@/lib/routing-validation";
import { useState, useEffect, useMemo } from "react";
import {
  Plus,
  Trash2,
  Save,
  CheckCircle,
  ChevronUp,
  ChevronDown,
  Info,
  Sparkles,
  AlertCircle,
  Copy,
  FileCode2,
} from "lucide-react";
import { toRoutingYaml } from "@/lib/routing-yaml";

const COMMON_LABELS = ["severity", "stage", "namespace", "alertname", "cluster", "job"];

const RULE_TEMPLATES: { label: string; description: string; rule: RoutingRule }[] = [
  {
    label: "Critical prod",
    description: "severity=critical in production",
    rule: {
      match: { severity: "critical", stage: "prod" },
      slack_webhook_url: "",
    },
  },
  {
    label: "SIT / staging",
    description: "stage matches sit or staging",
    rule: {
      match_re: { stage: "sit|staging" },
      slack_webhook_url: "",
    },
  },
  {
    label: "Kafka alerts",
    description: "alertname starts with msk. or NetworkKafka",
    rule: {
      match_re: { alertname: "^(msk\\.|NetworkKafka).*" },
      slack_webhook_url: "",
    },
  },
  {
    label: "EC2 host",
    description: "alertname starts with EC2Host",
    rule: {
      match_re: { alertname: "^EC2Host.*" },
      slack_webhook_url: "",
    },
  },
];

function ruleToConditions(rule: RoutingRule): LabelCondition[] {
  const conditions: LabelCondition[] = [];
  for (const [key, value] of Object.entries(rule.match ?? {})) {
    conditions.push({ key, kind: "exact", value });
  }
  for (const [key, value] of Object.entries(rule.match_re ?? {})) {
    conditions.push({ key, kind: "regex", value });
  }
  return conditions.length ? conditions : [{ key: "", kind: "exact", value: "" }];
}

function conditionsToRule(conditions: LabelCondition[], webhook: string): RoutingRule {
  const match: Record<string, string> = {};
  const match_re: Record<string, string> = {};
  for (const c of conditions) {
    const key = c.key.trim();
    if (!key) continue;
    if (c.kind === "exact") match[key] = c.value;
    else match_re[key] = c.value;
  }
  return {
    ...(Object.keys(match).length ? { match } : {}),
    ...(Object.keys(match_re).length ? { match_re } : {}),
    slack_webhook_url: webhook,
  };
}

const newEditableRule = (rule?: RoutingRule): EditableRule => ({
  id: crypto.randomUUID(),
  conditions: ruleToConditions(rule ?? { slack_webhook_url: "" }),
  slack_webhook_url: rule?.slack_webhook_url ?? "",
  mute_time_intervals: rule?.mute_time_intervals ?? [],
});

function editableToRoutingRule(rule: EditableRule): RoutingRule {
  const base = conditionsToRule(rule.conditions, rule.slack_webhook_url);
  if (rule.mute_time_intervals.length) {
    base.mute_time_intervals = rule.mute_time_intervals;
  }
  return base;
}

function describeRule(rule: RoutingRule): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(rule.match ?? {})) {
    parts.push(`${key} = ${value}`);
  }
  for (const [key, value] of Object.entries(rule.match_re ?? {})) {
    parts.push(`${key} ~ /${value}/`);
  }
  if (!parts.length) return "No label conditions (matches nothing)";
  return parts.join(" AND ");
}

function ConditionRow({
  condition,
  onChange,
  onDelete,
  canDelete,
  error,
}: {
  condition: LabelCondition;
  onChange: (c: LabelCondition) => void;
  onDelete: () => void;
  canDelete: boolean;
  error?: string;
}) {
  const inputClass = (invalid?: boolean) =>
    `input text-sm ${invalid ? "border-red-400 dark:border-red-500 focus:ring-red-400/40" : ""}`;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          className={`${inputClass(Boolean(error))} flex-1 min-w-[7rem]`}
          list="routing-label-keys"
          value={condition.key}
          onChange={(e) => onChange({ ...condition, key: e.target.value })}
          placeholder="label key"
        />
        <select
          className={`${inputClass()} w-36 shrink-0`}
          value={condition.kind}
          onChange={(e) => onChange({ ...condition, kind: e.target.value as LabelCondition["kind"] })}
        >
          <option value="exact">equals</option>
          <option value="regex">matches regex</option>
        </select>
        <input
          className={`${inputClass(Boolean(error))} flex-[2] min-w-[10rem] font-mono`}
          value={condition.value}
          onChange={(e) => onChange({ ...condition, value: e.target.value })}
          placeholder={condition.kind === "exact" ? "critical" : "^EC2Host.*"}
        />
        <button
          type="button"
          className="btn-ghost p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 shrink-0 disabled:opacity-30"
          onClick={onDelete}
          disabled={!canDelete}
          aria-label="Remove condition"
        >
          <Trash2 size={14} />
        </button>
      </div>
      {error && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>}
    </div>
  );
}

function RuleCard({
  index,
  rule,
  total,
  errors,
  intervalNames,
  onChange,
  onDelete,
  onMoveUp,
  onMoveDown,
}: {
  index: number;
  rule: EditableRule;
  total: number;
  errors?: RoutingValidation["rules"][string];
  intervalNames: string[];
  onChange: (r: EditableRule) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const routingRule = editableToRoutingRule(rule);
  const hasErrors = Boolean(
    errors?.general || errors?.webhook || errors?.muteIntervals || Object.keys(errors?.conditions ?? {}).length,
  );

  const updateConditions = (conditions: LabelCondition[]) => {
    onChange({ ...rule, conditions });
  };

  return (
    <div
      className={`border rounded-xl p-4 space-y-4 bg-slate-50 dark:bg-slate-800/50 ${
        hasErrors
          ? "border-red-300 dark:border-red-800"
          : "border-slate-200 dark:border-slate-700"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge-gray">Rule {index + 1}</span>
            {index === 0 && <span className="text-xs text-slate-400">checked first</span>}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 font-mono">
            {describeRule(routingRule)}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            className="btn-ghost p-2 disabled:opacity-30"
            onClick={onMoveUp}
            disabled={index === 0}
            aria-label="Move rule up"
          >
            <ChevronUp size={14} />
          </button>
          <button
            type="button"
            className="btn-ghost p-2 disabled:opacity-30"
            onClick={onMoveDown}
            disabled={index === total - 1}
            aria-label="Move rule down"
          >
            <ChevronDown size={14} />
          </button>
          <button
            type="button"
            className="btn-ghost p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30"
            onClick={onDelete}
            aria-label="Delete rule"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-slate-600 dark:text-slate-300">
          When <span className="font-semibold">all</span> of these label conditions match:
        </p>
        {errors?.general && (
          <p className="text-xs text-red-600 dark:text-red-400">{errors.general}</p>
        )}
        {rule.conditions.map((condition, i) => (
          <ConditionRow
            key={i}
            condition={condition}
            canDelete={rule.conditions.length > 1}
            error={errors?.conditions[i]}
            onChange={(c) => {
              const next = rule.conditions.map((x, j) => (j === i ? c : x));
              updateConditions(next);
            }}
            onDelete={() => updateConditions(rule.conditions.filter((_, j) => j !== i))}
          />
        ))}
        <button
          type="button"
          className="btn-ghost text-xs px-2 py-1"
          onClick={() =>
            updateConditions([
              ...rule.conditions,
              { key: "", kind: "exact", value: "" },
            ])
          }
        >
          <Plus size={12} /> Add condition
        </button>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
          Mute during time intervals (optional)
        </label>
        {intervalNames.length === 0 ? (
          <p className="text-xs text-slate-400">
            No time intervals defined.{" "}
            <a href="/time-intervals" className="text-primary hover:underline">
              Create intervals
            </a>
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {intervalNames.map((name) => (
              <label key={name} className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={rule.mute_time_intervals.includes(name)}
                  onChange={(e) => {
                    const set = new Set(rule.mute_time_intervals);
                    if (e.target.checked) set.add(name);
                    else set.delete(name);
                    onChange({ ...rule, mute_time_intervals: Array.from(set) });
                  }}
                />
                {name}
              </label>
            ))}
          </div>
        )}
        {errors?.muteIntervals && (
          <p className="text-xs text-red-600 dark:text-red-400 mt-1">{errors.muteIntervals}</p>
        )}
        <p className="text-xs text-slate-400 mt-1">
          When active, this route is skipped and the next matching rule is used.
        </p>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
          Send to Slack webhook
        </label>
        <input
          className={`input ${
            errors?.webhook ? "border-red-400 dark:border-red-500 focus:ring-red-400/40" : ""
          }`}
          value={rule.slack_webhook_url}
          onChange={(e) => onChange({ ...rule, slack_webhook_url: e.target.value })}
          placeholder="https://hooks.slack.com/services/…"
        />
        {errors?.webhook && (
          <p className="text-xs text-red-600 dark:text-red-400 mt-1">{errors.webhook}</p>
        )}
      </div>
    </div>
  );
}

function YamlPreview({
  yaml,
  saved,
}: {
  yaml: string;
  saved: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(yaml);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <div
      className={`card sticky top-4 flex flex-col ${
        saved
          ? "border-emerald-300 dark:border-emerald-800 ring-1 ring-emerald-200 dark:ring-emerald-900/50"
          : ""
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <FileCode2 size={16} className="text-indigo-500 shrink-0" />
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              routing.yaml
            </h2>
            <p className="text-xs text-slate-400 dark:text-slate-500 truncate">
              {saved ? "Saved configuration" : "Live preview"}
            </p>
          </div>
        </div>
        <button type="button" className="btn-secondary text-xs px-2.5 py-1.5 shrink-0" onClick={copy}>
          <Copy size={12} />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {saved && (
        <p className="text-xs text-emerald-600 dark:text-emerald-400 mb-2 flex items-center gap-1">
          <CheckCircle size={12} /> Active on all agent replicas
        </p>
      )}
      <pre className="text-xs font-mono leading-relaxed text-slate-700 dark:text-slate-300 bg-slate-950/5 dark:bg-slate-950/40 rounded-lg p-3 overflow-auto max-h-[calc(100vh-10rem)] whitespace-pre-wrap break-all">
        {yaml}
      </pre>
    </div>
  );
}

export default function RoutingPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["routing"],
    queryFn: () => api.get<RoutingConfig>("/api/config/routing"),
  });

  const { data: intervalsData } = useQuery({
    queryKey: ["time-intervals"],
    queryFn: () => api.get<TimeIntervalsConfig>("/api/config/time-intervals"),
  });

  const intervalNames = useMemo(
    () => (intervalsData?.time_intervals ?? []).map((i) => i.name.trim()).filter(Boolean),
    [intervalsData],
  );

  const [defaultUrl, setDefaultUrl] = useState("");
  const [rules, setRules] = useState<EditableRule[]>([]);
  const [saved, setSaved] = useState(false);
  const [validation, setValidation] = useState<RoutingValidation | null>(null);
  const [savedYaml, setSavedYaml] = useState<string | null>(null);

  const routingConfig = useMemo(
    () => ({
      default_slack_webhook_url: defaultUrl,
      routes: rules.map(editableToRoutingRule),
    }),
    [defaultUrl, rules],
  );

  const yamlPreview = useMemo(() => toRoutingYaml(routingConfig), [routingConfig]);

  const clearValidation = () => setValidation(null);

  useEffect(() => {
    if (data) {
      const loadedDefault = data.default_slack_webhook_url ?? "";
      const loadedRoutes = data.routes ?? [];
      setDefaultUrl(loadedDefault);
      setRules(loadedRoutes.map((r) => newEditableRule(r)));
      setSavedYaml(
        toRoutingYaml({
          default_slack_webhook_url: loadedDefault,
          routes: loadedRoutes,
        }),
      );
      setValidation(null);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: () => api.post("/api/config/routing", routingConfig),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["routing"] });
      setValidation(null);
      setSavedYaml(yamlPreview);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const handleSave = () => {
    const result = validateRouting(defaultUrl, rules, intervalNames);
    setValidation(result);
    if (!result.valid) return;
    mutation.mutate();
  };

  const moveRule = (from: number, to: number) => {
    setRules((rs) => {
      const next = [...rs];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
  };

  const addTemplate = (template: RoutingRule) => {
    setRules((rs) => [...rs, newEditableRule(template)]);
  };

  if (isLoading) return <div className="card h-64 animate-pulse" />;

  return (
    <div className="max-w-6xl">
      <datalist id="routing-label-keys">
        {COMMON_LABELS.map((label) => (
          <option key={label} value={label} />
        ))}
      </datalist>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_26rem] gap-6 items-start">
        <div className="min-w-0">

      <div className="mb-6">
        <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">
          Routing Rules
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Choose which Slack channel receives each alert based on its labels.
        </p>
      </div>

      <div className="card mb-6 border-indigo-200 dark:border-indigo-900/50 bg-indigo-50/50 dark:bg-indigo-950/20">
        <div className="flex gap-3">
          <Info size={18} className="text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
          <div className="text-sm text-slate-600 dark:text-slate-300 space-y-2">
            <p className="font-medium text-slate-800 dark:text-slate-100">How routing works</p>
            <ol className="list-decimal list-inside space-y-1 text-slate-600 dark:text-slate-400">
              <li>Alertmanager sends alerts with labels like <code className="text-xs bg-white/70 dark:bg-slate-800 px-1 rounded">severity</code>, <code className="text-xs bg-white/70 dark:bg-slate-800 px-1 rounded">stage</code>, <code className="text-xs bg-white/70 dark:bg-slate-800 px-1 rounded">alertname</code>.</li>
              <li>Rules are checked <strong>top to bottom</strong> — the first rule whose conditions all match wins.</li>
              <li>If no rule matches, the alert goes to the <strong>default webhook</strong> below.</li>
            </ol>
            <p className="text-xs text-slate-500 dark:text-slate-400 pt-1">
              Use <strong>equals</strong> for exact values (e.g. <code className="font-mono">severity</code> = <code className="font-mono">critical</code>).
              Use <strong>matches regex</strong> for patterns (e.g. <code className="font-mono">alertname</code> ~ <code className="font-mono">^EC2Host.*</code>).
            </p>
          </div>
        </div>
      </div>

      <div className="card mb-6">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
          Default Slack webhook
        </label>
        <input
          className={`input ${
            validation?.defaultUrl
              ? "border-red-400 dark:border-red-500 focus:ring-red-400/40"
              : ""
          }`}
          value={defaultUrl}
          onChange={(e) => {
            setDefaultUrl(e.target.value);
            clearValidation();
          }}
          placeholder="https://hooks.slack.com/services/…"
        />
        {validation?.defaultUrl ? (
          <p className="text-xs text-red-600 dark:text-red-400 mt-1.5">{validation.defaultUrl}</p>
        ) : (
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1.5">
            Fallback when no rule matches. You can also set <code className="font-mono">SLACK_WEBHOOK_URL</code> in
            your environment — leave this empty to rely on that.
          </p>
        )}
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Rules</h2>
          <span className="text-xs text-slate-400">{rules.length} rule{rules.length === 1 ? "" : "s"}</span>
        </div>

        <div className="space-y-3 mb-4">
          {rules.map((rule, i) => (
            <RuleCard
              key={rule.id}
              index={i}
              total={rules.length}
              rule={rule}
              intervalNames={intervalNames}
              errors={validation?.rules[rule.id]}
              onChange={(r) => {
                clearValidation();
                setRules((rs) => rs.map((x, j) => (j === i ? r : x)));
              }}
              onDelete={() => setRules((rs) => rs.filter((_, j) => j !== i))}
              onMoveUp={() => moveRule(i, i - 1)}
              onMoveDown={() => moveRule(i, i + 1)}
            />
          ))}
          {rules.length === 0 && (
            <div className="text-center py-10 border border-dashed border-slate-200 dark:border-slate-700 rounded-xl">
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-1">No routing rules yet</p>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                All alerts will use the default webhook above.
              </p>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 mb-4 bg-white dark:bg-slate-800/30">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={14} className="text-indigo-500" />
            <p className="text-xs font-medium text-slate-600 dark:text-slate-300">Quick-start templates</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {RULE_TEMPLATES.map((t) => (
              <button
                key={t.label}
                type="button"
                className="btn-secondary text-xs px-3 py-1.5"
                title={t.description}
                onClick={() => addTemplate(t.rule)}
              >
                <Plus size={12} /> {t.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">
            Adds a pre-filled rule — you still need to paste the Slack webhook URL and save.
          </p>
        </div>
      </div>

      {validation && !validation.valid && (
        <div className="card mb-4 border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/20">
          <div className="flex gap-3">
            <AlertCircle size={18} className="text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-800 dark:text-red-200">
                Fix the errors below before saving
              </p>
              <ul className="mt-1 text-xs text-red-700 dark:text-red-300 list-disc list-inside space-y-0.5">
                {validation.global.map((msg) => (
                  <li key={msg}>{msg}</li>
                ))}
                {validation.defaultUrl && <li>{validation.defaultUrl}</li>}
              </ul>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            clearValidation();
            setRules((r) => [...r, newEditableRule()]);
          }}
        >
          <Plus size={14} /> Add blank rule
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={handleSave}
          disabled={mutation.isPending}
        >
          <Save size={14} /> {mutation.isPending ? "Saving…" : "Save routing"}
        </button>
        {saved && (
          <span className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
            <CheckCircle size={14} /> Saved — active on all agent replicas
          </span>
        )}
        {mutation.isError && (
          <span className="text-sm text-red-600 dark:text-red-400">
            {(mutation.error as Error).message}
          </span>
        )}
      </div>
        </div>

        <aside className="min-w-0">
          <YamlPreview
            yaml={yamlPreview}
            saved={saved || (savedYaml !== null && savedYaml === yamlPreview)}
          />
        </aside>
      </div>
    </div>
  );
}
