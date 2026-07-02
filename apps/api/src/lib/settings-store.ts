import * as fs from "fs";
import * as path from "path";
import { load as yamlLoad } from "js-yaml";
import { Db, ObjectId } from "mongodb";
import { getDb } from "./mongo";
import { maskAgentSettings, maskEndpoint, mergeAgentSecrets, mergeEndpointSecrets } from "./secrets";
import type {
  AgentConfig,
  Endpoint,
  Environment,
  NamedTimeInterval,
  RoutingConfig,
  RoutingRule,
  SilenceRule,
  SilencesConfig,
  TimeIntervalsConfig,
} from "@shared/types";
import { validateEndpoints, toEndpointsConfig, fromEndpointsConfig } from "@shared/validation/endpoints-validation";
import { validateEnvironments, toEnvConfig } from "@shared/validation/environments-validation";
import { validateRouting } from "@shared/validation/routing-validation";
import { validateTimeIntervals } from "@shared/validation/time-intervals-validation";

export const CONFIGURABLE_KEYS = [
  "AI_PROVIDER",
  "OPENAI_MODEL",
  "OPENAI_MODEL_INFO",
  "OPENAI_API_KEY",
  "OPENAI_BASE_URL",
  "ANTHROPIC_API_KEY",
  "GEMINI_API_KEY",
  "GOOGLE_SA_JSON",
  "GOOGLE_CLOUD_PROJECT",
  "GOOGLE_CLOUD_LOCATION",
  "GOOGLE_GENAI_USE_VERTEXAI",
  "AWS_REGION",
  "AWS_ROLE_ARN",
  "LLM_ENABLED",
  "SLACK_WEBHOOK_URL",
  "PROMETHEUS_URL",
  "LOKI_URL",
  "LOGS_DIR",
  "DEDUP_TTL_SECONDS",
  "ALLOWED_ALERTNAMES",
  "ALERT_CATALOG_PATH",
  "ROUTING_CONFIG_PATH",
] as const;

const DEFAULTS: Record<string, unknown> = {
  AI_PROVIDER: "openai",
  OPENAI_MODEL: "gpt-4o",
  OPENAI_MODEL_INFO: "gpt-4o-mini",
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
  SLACK_WEBHOOK_URL: "",
  PROMETHEUS_URL: "http://service-gps.monitoring.svc.cluster.local:9090",
  LOKI_URL: "http://localhost:3100",
  LOGS_DIR: "/app/logs",
  DEDUP_TTL_SECONDS: 900,
  ALLOWED_ALERTNAMES: "",
  ALERT_CATALOG_PATH: "/app/config/alert_catalog.yaml",
  ROUTING_CONFIG_PATH: "",
};

const RUNTIME_ID = "runtime";
const META_ID = "version";
const ROUTING_META_ID = "meta";

type StringIdDoc = { _id: string };
type SettingsMetaDoc = { _id: string; version?: number; updated_at?: Date };
type RoutingSettingsDoc = { _id: string; default_slack_webhook_url?: string };
type AgentSettingsDoc = { _id: string; [key: string]: unknown };

async function bumpVersion(db: Db): Promise<void> {
  await db.collection<SettingsMetaDoc>("settings_meta").updateOne(
    { _id: META_ID },
    { $inc: { version: 1 }, $set: { updated_at: new Date() } },
    { upsert: true }
  );
}

export async function getSettingsVersion(): Promise<number> {
  const db = await getDb();
  const doc = await db.collection<SettingsMetaDoc>("settings_meta").findOne({ _id: META_ID });
  return (doc?.version as number) ?? 0;
}

// ── Agent settings ────────────────────────────────────────────────────────────

export async function getAgentSettings(masked = true): Promise<Record<string, unknown>> {
  const db = await getDb();
  const doc = await db.collection<AgentSettingsDoc>("agent_settings").findOne({ _id: RUNTIME_ID });
  const stored = (doc ?? {}) as Record<string, unknown>;
  delete stored._id;
  const result: Record<string, unknown> = {};
  for (const key of CONFIGURABLE_KEYS) {
    result[key] = stored[key] ?? process.env[key] ?? DEFAULTS[key] ?? "";
  }
  return masked ? maskAgentSettings(result) : result;
}

export async function updateAgentSettings(updates: Record<string, unknown>): Promise<Record<string, unknown>> {
  const db = await getDb();
  const stored = await getAgentSettings(false);
  const accepted: Record<string, unknown> = {};
  for (const key of CONFIGURABLE_KEYS) {
    if (key in updates) accepted[key] = updates[key];
  }
  if (!Object.keys(accepted).length) return getAgentSettings(true);
  const merged = mergeAgentSecrets({ ...stored, ...accepted }, stored);
  await db.collection<AgentSettingsDoc>("agent_settings").updateOne(
    { _id: RUNTIME_ID },
    { $set: merged },
    { upsert: true }
  );
  await bumpVersion(db);
  return getAgentSettings(true);
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

function stripMongo<T extends Record<string, unknown>>(doc: T | null): Omit<T, "_id"> | null {
  if (!doc) return null;
  const { _id, ...rest } = doc;
  return rest as Omit<T, "_id">;
}

export async function listEndpoints(q?: string, type?: string): Promise<Endpoint[]> {
  const db = await getDb();
  const filter: Record<string, unknown> = {};
  if (type) filter.type = type;
  const docs = await db.collection("endpoints").find(filter).sort({ name: 1 }).toArray();
  let eps = docs.map((d) => stripMongo(d as Record<string, unknown>) as unknown as unknown as Endpoint);
  if (q) {
    const lower = q.toLowerCase();
    eps = eps.filter(
      (e) =>
        e.name.toLowerCase().includes(lower) ||
        (e.url || "").toLowerCase().includes(lower) ||
        (e.region || "").toLowerCase().includes(lower)
    );
  }
  return eps.map(maskEndpoint);
}

export async function getEndpoint(name: string): Promise<Endpoint | null> {
  const db = await getDb();
  const doc = await db.collection("endpoints").findOne({ name });
  return doc ? maskEndpoint(stripMongo(doc as Record<string, unknown>) as unknown as Endpoint) : null;
}

export async function getEndpointRaw(name: string): Promise<Endpoint | null> {
  const db = await getDb();
  const doc = await db.collection("endpoints").findOne({ name });
  return doc ? (stripMongo(doc as Record<string, unknown>) as unknown as Endpoint) : null;
}

function validateSingleEndpoint(ep: Endpoint): string[] {
  const editable = fromEndpointsConfig({ endpoints: [ep] });
  const v = validateEndpoints(editable);
  return v.eps[editable[0]?.id] ? [v.eps[editable[0].id]] : [];
}

export async function createEndpoint(ep: Endpoint): Promise<Endpoint> {
  const errors = validateSingleEndpoint(ep);
  if (errors.length) throw new ValidationError(errors);
  const db = await getDb();
  const existing = await db.collection("endpoints").findOne({ name: ep.name.trim() });
  if (existing) throw new ValidationError([`Endpoint "${ep.name}" already exists.`]);
  const doc = { ...ep, name: ep.name.trim() };
  await db.collection("endpoints").insertOne(doc);
  await bumpVersion(db);
  return maskEndpoint(doc);
}

export async function updateEndpoint(name: string, ep: Endpoint): Promise<Endpoint> {
  const db = await getDb();
  const stored = await getEndpointRaw(name);
  if (!stored) throw new NotFoundError(`Endpoint "${name}" not found`);
  const merged = mergeEndpointSecrets({ ...ep, name: ep.name.trim() }, stored);
  const errors = validateSingleEndpoint(merged);
  if (errors.length) throw new ValidationError(errors);
  if (ep.name.trim() !== name) {
    const clash = await db.collection("endpoints").findOne({ name: ep.name.trim() });
    if (clash) throw new ValidationError([`Endpoint "${ep.name}" already exists.`]);
  }
  await db.collection("endpoints").deleteOne({ name });
  await db.collection("endpoints").insertOne(merged);
  await bumpVersion(db);
  return maskEndpoint(merged);
}

export async function deleteEndpoint(name: string): Promise<void> {
  const db = await getDb();
  const res = await db.collection("endpoints").deleteOne({ name });
  if (!res.deletedCount) throw new NotFoundError(`Endpoint "${name}" not found`);
  await bumpVersion(db);
}

export async function endpointsByType(): Promise<Record<string, string>> {
  const eps = await listEndpoints();
  const map: Record<string, string> = {};
  for (const e of eps) map[e.name] = e.type;
  return map;
}

// ── Environments ────────────────────────────────────────────────────────────

export async function listEnvironments(q?: string): Promise<Environment[]> {
  const db = await getDb();
  const docs = await db.collection("environments").find({}).sort({ name: 1 }).toArray();
  let envs = docs.map((d) => stripMongo(d as Record<string, unknown>) as unknown as Environment);
  if (q) {
    const lower = q.toLowerCase();
    envs = envs.filter((e) => e.name.toLowerCase().includes(lower));
  }
  return envs;
}

export async function getEnvironment(name: string): Promise<Environment | null> {
  const db = await getDb();
  const doc = await db.collection("environments").findOne({ name });
  return doc ? (stripMongo(doc as Record<string, unknown>) as unknown as Environment) : null;
}

async function validateEnvironment(env: Environment): Promise<string[]> {
  const byType = await endpointsByType();
  const editable = [{ id: "x", name: env.name, prometheus: env.prometheus ?? "", loki: env.loki ?? "", kubernetes: env.kubernetes ?? "", aws: env.aws ?? "" }];
  const v = validateEnvironments(editable, byType);
  return Object.values(v.envs);
}

export async function createEnvironment(env: Environment): Promise<Environment> {
  const name = env.name.trim();
  const errors = await validateEnvironment({ ...env, name });
  if (errors.length) throw new ValidationError(errors);
  const db = await getDb();
  if (await db.collection("environments").findOne({ name })) {
    throw new ValidationError([`Environment "${name}" already exists.`]);
  }
  const doc = { ...env, name };
  await db.collection("environments").insertOne(doc);
  await bumpVersion(db);
  return doc;
}

export async function updateEnvironment(name: string, env: Environment): Promise<Environment> {
  const db = await getDb();
  if (!(await db.collection("environments").findOne({ name }))) {
    throw new NotFoundError(`Environment "${name}" not found`);
  }
  const newName = env.name.trim();
  const errors = await validateEnvironment({ ...env, name: newName });
  if (errors.length) throw new ValidationError(errors);
  if (newName !== name && (await db.collection("environments").findOne({ name: newName }))) {
    throw new ValidationError([`Environment "${newName}" already exists.`]);
  }
  const doc = { ...env, name: newName };
  await db.collection("environments").deleteOne({ name });
  await db.collection("environments").insertOne(doc);
  await bumpVersion(db);
  return doc;
}

export async function deleteEnvironment(name: string): Promise<void> {
  const db = await getDb();
  const res = await db.collection("environments").deleteOne({ name });
  if (!res.deletedCount) throw new NotFoundError(`Environment "${name}" not found`);
  await bumpVersion(db);
}

// ── Routing ───────────────────────────────────────────────────────────────────

export type RoutingRuleDoc = RoutingRule & { id: string; order: number };

export async function getRoutingConfig(): Promise<RoutingConfig> {
  const db = await getDb();
  const meta = await db.collection<RoutingSettingsDoc>("routing_settings").findOne({ _id: ROUTING_META_ID });
  const rules = await db
    .collection("routing_rules")
    .find({})
    .sort({ order: 1 })
    .toArray();
  return {
    default_slack_webhook_url: (meta?.default_slack_webhook_url as string) || "",
    routes: rules.map((r) => {
      const { id, order, ...rule } = stripMongo(r as Record<string, unknown>) as unknown as RoutingRuleDoc;
      return rule as RoutingRule;
    }),
  };
}

export async function updateRoutingMeta(defaultUrl: string): Promise<void> {
  const db = await getDb();
  await db.collection<RoutingSettingsDoc>("routing_settings").updateOne(
    { _id: ROUTING_META_ID },
    { $set: { default_slack_webhook_url: defaultUrl } },
    { upsert: true }
  );
  await bumpVersion(db);
}

export async function listRoutingRules(): Promise<RoutingRuleDoc[]> {
  const db = await getDb();
  const rules = await db.collection("routing_rules").find({}).sort({ order: 1 }).toArray();
  return rules.map((r) => stripMongo(r as Record<string, unknown>) as unknown as RoutingRuleDoc);
}

export async function createRoutingRule(rule: RoutingRule): Promise<RoutingRuleDoc> {
  const db = await getDb();
  const count = await db.collection("routing_rules").countDocuments();
  const id = crypto.randomUUID();
  const doc: RoutingRuleDoc = { ...rule, id, order: count };
  await db.collection("routing_rules").insertOne(doc);
  await bumpVersion(db);
  return doc;
}

export async function updateRoutingRule(id: string, rule: RoutingRule): Promise<RoutingRuleDoc> {
  const db = await getDb();
  const existing = await db.collection("routing_rules").findOne({ id });
  if (!existing) throw new NotFoundError(`Rule "${id}" not found`);
  const doc: RoutingRuleDoc = { ...rule, id, order: (existing.order as number) ?? 0 };
  await db.collection("routing_rules").replaceOne({ id }, doc);
  await bumpVersion(db);
  return doc;
}

export async function deleteRoutingRule(id: string): Promise<void> {
  const db = await getDb();
  const res = await db.collection("routing_rules").deleteOne({ id });
  if (!res.deletedCount) throw new NotFoundError(`Rule "${id}" not found`);
  await bumpVersion(db);
}

export async function reorderRoutingRules(ids: string[]): Promise<void> {
  const db = await getDb();
  for (let i = 0; i < ids.length; i++) {
    await db.collection("routing_rules").updateOne({ id: ids[i] }, { $set: { order: i } });
  }
  await bumpVersion(db);
}

// ── Time intervals ──────────────────────────────────────────────────────────

export type TimeIntervalDoc = NamedTimeInterval & { order: number };

export async function getTimeIntervalsConfig(): Promise<TimeIntervalsConfig> {
  const db = await getDb();
  const docs = await db.collection("time_intervals").find({}).sort({ order: 1 }).toArray();
  return {
    time_intervals: docs.map((d) => {
      const { order, ...rest } = stripMongo(d as Record<string, unknown>) as unknown as TimeIntervalDoc;
      return rest as NamedTimeInterval;
    }),
  };
}

export async function getTimeIntervalNames(): Promise<string[]> {
  const cfg = await getTimeIntervalsConfig();
  return cfg.time_intervals.map((i) => i.name.trim()).filter(Boolean);
}

export async function createTimeInterval(interval: NamedTimeInterval): Promise<TimeIntervalDoc> {
  const db = await getDb();
  const count = await db.collection("time_intervals").countDocuments();
  const doc: TimeIntervalDoc = { ...interval, order: count };
  await db.collection("time_intervals").insertOne(doc);
  await bumpVersion(db);
  return doc;
}

export async function updateTimeInterval(name: string, interval: NamedTimeInterval): Promise<TimeIntervalDoc> {
  const db = await getDb();
  const existing = await db.collection("time_intervals").findOne({ name });
  if (!existing) throw new NotFoundError(`Interval "${name}" not found`);
  const doc: TimeIntervalDoc = { ...interval, order: (existing.order as number) ?? 0 };
  if (interval.name.trim() !== name) {
    await db.collection("time_intervals").deleteOne({ name });
    await db.collection("time_intervals").insertOne(doc);
  } else {
    await db.collection("time_intervals").replaceOne({ name }, doc);
  }
  await bumpVersion(db);
  return doc;
}

export async function deleteTimeInterval(name: string): Promise<void> {
  const db = await getDb();
  const res = await db.collection("time_intervals").deleteOne({ name });
  if (!res.deletedCount) throw new NotFoundError(`Interval "${name}" not found`);
  await bumpVersion(db);
}

export async function reorderTimeIntervals(names: string[]): Promise<void> {
  const db = await getDb();
  for (let i = 0; i < names.length; i++) {
    await db.collection("time_intervals").updateOne({ name: names[i] }, { $set: { order: i } });
  }
  await bumpVersion(db);
}

// ── Silences ──────────────────────────────────────────────────────────────────

export type SilenceDoc = SilenceRule & { status: "active" | "disabled" };

export async function getSilencesConfig(): Promise<SilencesConfig> {
  const db = await getDb();
  const docs = await db.collection("silences").find({}).toArray();
  const active: SilenceRule[] = [];
  const disabled: SilenceRule[] = [];
  for (const d of docs) {
    const { status, ...rule } = stripMongo(d as Record<string, unknown>) as unknown as SilenceDoc;
    if (status === "disabled") disabled.push(rule);
    else active.push(rule);
  }
  return { silences: { active, disabled } };
}

export async function listSilences(status?: "active" | "disabled"): Promise<SilenceRule[]> {
  const cfg = await getSilencesConfig();
  if (status === "active") return cfg.silences.active;
  if (status === "disabled") return cfg.silences.disabled;
  return [...cfg.silences.active, ...cfg.silences.disabled];
}

export async function createSilence(rule: SilenceRule): Promise<SilenceRule> {
  const db = await getDb();
  const id = rule.id || crypto.randomUUID();
  const doc: SilenceDoc = { ...rule, id, status: "active" };
  await db.collection("silences").insertOne(doc);
  await bumpVersion(db);
  return { ...rule, id };
}

export async function updateSilence(id: string, rule: SilenceRule, status: "active" | "disabled" = "active"): Promise<SilenceRule> {
  const db = await getDb();
  const existing = await db.collection("silences").findOne({ id });
  if (!existing) throw new NotFoundError(`Silence "${id}" not found`);
  const doc: SilenceDoc = { ...rule, id, status };
  await db.collection("silences").replaceOne({ id }, doc);
  await bumpVersion(db);
  return rule;
}

export async function deleteSilence(id: string): Promise<void> {
  const db = await getDb();
  const res = await db.collection("silences").deleteOne({ id });
  if (!res.deletedCount) throw new NotFoundError(`Silence "${id}" not found`);
  await bumpVersion(db);
}

export async function disableSilence(id: string): Promise<void> {
  const db = await getDb();
  const doc = await db.collection("silences").findOne({ id, status: "active" });
  if (!doc) throw new NotFoundError(`Silence "${id}" not found in active list`);
  await db.collection("silences").updateOne(
    { id },
    {
      $set: {
        status: "disabled",
        disabled_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
        disabled_reason: "manual",
      },
    }
  );
  await bumpVersion(db);
}

export async function enableSilence(id: string, patch?: Partial<SilenceRule>): Promise<void> {
  const db = await getDb();
  const doc = await db.collection("silences").findOne({ id, status: "disabled" });
  if (!doc) throw new NotFoundError(`Silence "${id}" not found in disabled list`);
  const mode = patch?.mode || doc.mode || "permanent";
  const set: Record<string, unknown> = { status: "active", mode };
  if (mode === "until") set.ends_at = patch?.ends_at || doc.ends_at;
  await db.collection("silences").updateOne(
    { id },
    { $set: set, $unset: { disabled_at: "", disabled_reason: "" } }
  );
  await bumpVersion(db);
}

// ── Reports (Mongo events) ────────────────────────────────────────────────────

export async function reportSummary(days: number) {
  const db = await getDb();
  const now = new Date();
  const start = new Date(now.getTime() - days * 86400000);
  const events = await db
    .collection("alert_events")
    .find({ ts: { $gte: start, $lte: now } })
    .toArray();
  const by_alertname: Record<string, { rca: number; incoming: number; cost_usd?: number }> = {};
  const hourly: Record<string, number> = {};
  let totalCost = 0;
  let totalTokens = 0;
  const cost_by_model: Record<string, number> = {};
  for (const e of events) {
    const name = (e.alertname as string) || "unknown";
    if (!by_alertname[name]) by_alertname[name] = { rca: 0, incoming: 0, cost_usd: 0 };
    const outcome = e.outcome as string;
    if (outcome === "rca_success" || outcome === "rca_slack_error") by_alertname[name].rca++;
    else if (outcome === "accepted") by_alertname[name].incoming++;
    const cost = (e.cost_usd as number) || 0;
    by_alertname[name].cost_usd = (by_alertname[name].cost_usd || 0) + cost;
    totalCost += cost;
    totalTokens += (e.total_tokens as number) || 0;
    const model = (e.model as string) || "unknown";
    cost_by_model[model] = (cost_by_model[model] || 0) + cost;
    if (e.ts) {
      const h = new Date(e.ts as Date).toISOString().slice(0, 13) + ":00Z";
      hourly[h] = (hourly[h] || 0) + 1;
    }
  }
  const timeline = Object.entries(hourly)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([hour, count]) => ({ hour, count }));
  const total = Object.values(by_alertname).reduce((s, v) => s + v.rca + v.incoming, 0);
  return {
    source: "mongo" as const,
    files: total,
    by_alertname,
    timeline,
    totals: { events: events.length, cost_usd: totalCost, total_tokens: totalTokens },
    cost_by_model,
    days,
  };
}

export async function recentEvents(opts: {
  days: number;
  alertname?: string;
  outcome?: string;
  limit: number;
  skip: number;
}) {
  const db = await getDb();
  const now = new Date();
  const start = new Date(now.getTime() - opts.days * 86400000);
  const filter: Record<string, unknown> = { ts: { $gte: start, $lte: now } };
  if (opts.alertname) filter.alertname = opts.alertname;
  if (opts.outcome) filter.outcome = opts.outcome;
  const events = await db
    .collection("alert_events")
    .find(filter)
    .sort({ ts: -1 })
    .skip(opts.skip)
    .limit(opts.limit)
    .toArray();
  return events.map((e) => {
    const { _id, ...rest } = e;
    return { ...rest, _id: _id instanceof ObjectId ? _id.toString() : _id };
  });
}

// ── Seed migration ────────────────────────────────────────────────────────────

function readYamlFile(filePath: string): unknown {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return yamlLoad(fs.readFileSync(filePath, "utf-8"));
}

function readJsonFile(filePath: string): unknown {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

const CONFIG_ROOT = process.env.CONFIG_ROOT || path.join(process.cwd(), '..', '..', 'config');

export async function seedIfEmpty(): Promise<void> {
  const db = await getDb();
  const epCount = await db.collection("endpoints").countDocuments();
  if (epCount > 0) return;

  const endpointsPath = process.env.ENDPOINTS_CONFIG_PATH || path.join(CONFIG_ROOT, "endpoints.yaml");
  const envsPath = process.env.ENVIRONMENTS_CONFIG_PATH || path.join(CONFIG_ROOT, "environments.yaml");
  const routingPath = process.env.ROUTING_CONFIG_PATH || path.join(CONFIG_ROOT, "routing.yaml");
  const silencesPath = process.env.SILENCES_CONFIG_PATH || path.join(CONFIG_ROOT, "silences.yaml");
  const intervalsPath = process.env.TIME_INTERVALS_CONFIG_PATH || path.join(CONFIG_ROOT, "time_intervals.yaml");
  const agentPath = process.env.CONFIG_STORE_PATH || path.join(CONFIG_ROOT, "web_config.json");

  const epData = readYamlFile(endpointsPath) as { endpoints?: Endpoint[] } | null;
  if (epData?.endpoints?.length) {
    await db.collection("endpoints").insertMany(epData.endpoints.map((e) => ({ ...e })));
  }

  const envData = readYamlFile(envsPath) as { environments?: Environment[] } | null;
  if (envData?.environments?.length) {
    await db.collection("environments").insertMany(envData.environments.map((e) => ({ ...e })));
  }

  const routingData = readYamlFile(routingPath) as RoutingConfig | null;
  if (routingData) {
    await db.collection<RoutingSettingsDoc>("routing_settings").updateOne(
      { _id: ROUTING_META_ID },
      { $set: { default_slack_webhook_url: routingData.default_slack_webhook_url || "" } },
      { upsert: true }
    );
    const routes = routingData.routes || [];
    await db.collection("routing_rules").insertMany(
      routes.map((r, i) => ({ ...r, id: crypto.randomUUID(), order: i }))
    );
  }

  const silencesData = readYamlFile(silencesPath) as SilencesConfig | null;
  if (silencesData?.silences) {
    const docs: SilenceDoc[] = [
      ...silencesData.silences.active.map((r) => ({ ...r, status: "active" as const })),
      ...silencesData.silences.disabled.map((r) => ({ ...r, status: "disabled" as const })),
    ];
    if (docs.length) await db.collection("silences").insertMany(docs);
  }

  const intervalsData = readYamlFile(intervalsPath) as TimeIntervalsConfig | null;
  if (intervalsData?.time_intervals?.length) {
    await db.collection("time_intervals").insertMany(
      intervalsData.time_intervals.map((t, i) => ({ ...t, order: i }))
    );
  }

  const agentData = readJsonFile(agentPath) as Record<string, unknown> | null;
  if (agentData && Object.keys(agentData).length) {
    await db.collection<AgentSettingsDoc>("agent_settings").updateOne(
      { _id: RUNTIME_ID },
      { $set: agentData },
      { upsert: true }
    );
  }

  await bumpVersion(db);
}

export class ValidationError extends Error {
  details: string[];
  constructor(details: string[]) {
    super("Validation failed");
    this.details = details;
  }
}

export class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
  }
}

// Legacy bulk helpers for /api/config compatibility
export async function saveEndpointsBulk(body: { endpoints: Endpoint[] }): Promise<void> {
  const db = await getDb();
  const stored = await db.collection("endpoints").find({}).toArray();
  const storedMap = new Map(stored.map((d) => [d.name as string, stripMongo(d as Record<string, unknown>) as unknown as Endpoint]));
  const merged = body.endpoints.map((ep) => mergeEndpointSecrets(ep, storedMap.get(ep.name)));
  const v = validateEndpoints(fromEndpointsConfig({ endpoints: merged }));
  if (!v.valid) throw new ValidationError(Object.values(v.eps));
  await db.collection("endpoints").deleteMany({});
  if (merged.length) await db.collection("endpoints").insertMany(merged);
  await bumpVersion(db);
}

export async function saveEnvironmentsBulk(body: { environments: Environment[] }): Promise<void> {
  const byType = await endpointsByType();
  const editable = body.environments.map((e, i) => ({
    id: `e-${i}`,
    name: e.name,
    prometheus: e.prometheus ?? "",
    loki: e.loki ?? "",
    kubernetes: e.kubernetes ?? "",
    aws: e.aws ?? "",
  }));
  const v = validateEnvironments(editable, byType);
  if (!v.valid) throw new ValidationError(Object.values(v.envs));
  const db = await getDb();
  await db.collection("environments").deleteMany({});
  if (body.environments.length) await db.collection("environments").insertMany(body.environments);
  await bumpVersion(db);
}

export async function saveRoutingBulk(body: RoutingConfig): Promise<void> {
  const db = await getDb();
  await db.collection<RoutingSettingsDoc>("routing_settings").updateOne(
    { _id: ROUTING_META_ID },
    { $set: { default_slack_webhook_url: body.default_slack_webhook_url || "" } },
    { upsert: true }
  );
  await db.collection("routing_rules").deleteMany({});
  const routes = body.routes || [];
  if (routes.length) {
    await db.collection("routing_rules").insertMany(
      routes.map((r, i) => ({ ...r, id: crypto.randomUUID(), order: i }))
    );
  }
  await bumpVersion(db);
}

export async function saveTimeIntervalsBulk(body: TimeIntervalsConfig): Promise<void> {
  const v = validateTimeIntervals(body.time_intervals || []);
  if (!v.valid) throw new ValidationError([...v.global, ...Object.values(v.intervals)]);
  const db = await getDb();
  await db.collection("time_intervals").deleteMany({});
  const intervals = body.time_intervals || [];
  if (intervals.length) {
    await db.collection("time_intervals").insertMany(intervals.map((t, i) => ({ ...t, order: i })));
  }
  await bumpVersion(db);
}

export async function saveSilencesBulk(body: SilencesConfig): Promise<void> {
  if (!body.silences?.active && !body.silences?.disabled) {
    throw new ValidationError(["Invalid silences config"]);
  }
  const db = await getDb();
  await db.collection("silences").deleteMany({});
  const docs: SilenceDoc[] = [
    ...body.silences.active.map((r) => ({ ...r, status: "active" as const })),
    ...body.silences.disabled.map((r) => ({ ...r, status: "disabled" as const })),
  ];
  if (docs.length) await db.collection("silences").insertMany(docs);
  await bumpVersion(db);
}

export type { AgentConfig };
