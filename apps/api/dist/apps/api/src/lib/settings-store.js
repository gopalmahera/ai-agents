"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NotFoundError = exports.ValidationError = exports.CONFIGURABLE_KEYS = void 0;
exports.getSettingsVersion = getSettingsVersion;
exports.getAgentSettings = getAgentSettings;
exports.updateAgentSettings = updateAgentSettings;
exports.listEndpoints = listEndpoints;
exports.getEndpoint = getEndpoint;
exports.getEndpointRaw = getEndpointRaw;
exports.createEndpoint = createEndpoint;
exports.updateEndpoint = updateEndpoint;
exports.deleteEndpoint = deleteEndpoint;
exports.endpointsByType = endpointsByType;
exports.listEnvironments = listEnvironments;
exports.getEnvironment = getEnvironment;
exports.createEnvironment = createEnvironment;
exports.updateEnvironment = updateEnvironment;
exports.deleteEnvironment = deleteEnvironment;
exports.getRoutingConfig = getRoutingConfig;
exports.updateRoutingMeta = updateRoutingMeta;
exports.listRoutingRules = listRoutingRules;
exports.createRoutingRule = createRoutingRule;
exports.updateRoutingRule = updateRoutingRule;
exports.deleteRoutingRule = deleteRoutingRule;
exports.reorderRoutingRules = reorderRoutingRules;
exports.getTimeIntervalsConfig = getTimeIntervalsConfig;
exports.getTimeIntervalNames = getTimeIntervalNames;
exports.createTimeInterval = createTimeInterval;
exports.updateTimeInterval = updateTimeInterval;
exports.deleteTimeInterval = deleteTimeInterval;
exports.reorderTimeIntervals = reorderTimeIntervals;
exports.getSilencesConfig = getSilencesConfig;
exports.listSilences = listSilences;
exports.createSilence = createSilence;
exports.updateSilence = updateSilence;
exports.deleteSilence = deleteSilence;
exports.disableSilence = disableSilence;
exports.enableSilence = enableSilence;
exports.reportSummary = reportSummary;
exports.recentEvents = recentEvents;
exports.seedIfEmpty = seedIfEmpty;
exports.saveEndpointsBulk = saveEndpointsBulk;
exports.saveEnvironmentsBulk = saveEnvironmentsBulk;
exports.saveRoutingBulk = saveRoutingBulk;
exports.saveTimeIntervalsBulk = saveTimeIntervalsBulk;
exports.saveSilencesBulk = saveSilencesBulk;
const fs_1 = require("fs");
const path_1 = require("path");
const js_yaml_1 = require("js-yaml");
const mongodb_1 = require("mongodb");
const mongo_1 = require("./mongo");
const secrets_1 = require("./secrets");
const endpoints_validation_1 = require("../../../../packages/shared/src/validation/endpoints-validation");
const environments_validation_1 = require("../../../../packages/shared/src/validation/environments-validation");
const time_intervals_validation_1 = require("../../../../packages/shared/src/validation/time-intervals-validation");
exports.CONFIGURABLE_KEYS = [
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
];
const DEFAULTS = {
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
async function bumpVersion(db) {
    await db.collection("settings_meta").updateOne({ _id: META_ID }, { $inc: { version: 1 }, $set: { updated_at: new Date() } }, { upsert: true });
}
async function getSettingsVersion() {
    const db = await (0, mongo_1.getDb)();
    const doc = await db.collection("settings_meta").findOne({ _id: META_ID });
    return doc?.version ?? 0;
}
async function getAgentSettings(masked = true) {
    const db = await (0, mongo_1.getDb)();
    const doc = await db.collection("agent_settings").findOne({ _id: RUNTIME_ID });
    const stored = (doc ?? {});
    delete stored._id;
    const result = {};
    for (const key of exports.CONFIGURABLE_KEYS) {
        result[key] = stored[key] ?? process.env[key] ?? DEFAULTS[key] ?? "";
    }
    return masked ? (0, secrets_1.maskAgentSettings)(result) : result;
}
async function updateAgentSettings(updates) {
    const db = await (0, mongo_1.getDb)();
    const stored = await getAgentSettings(false);
    const accepted = {};
    for (const key of exports.CONFIGURABLE_KEYS) {
        if (key in updates)
            accepted[key] = updates[key];
    }
    if (!Object.keys(accepted).length)
        return getAgentSettings(true);
    const merged = (0, secrets_1.mergeAgentSecrets)({ ...stored, ...accepted }, stored);
    await db.collection("agent_settings").updateOne({ _id: RUNTIME_ID }, { $set: merged }, { upsert: true });
    await bumpVersion(db);
    return getAgentSettings(true);
}
function stripMongo(doc) {
    if (!doc)
        return null;
    const { _id, ...rest } = doc;
    return rest;
}
async function listEndpoints(q, type) {
    const db = await (0, mongo_1.getDb)();
    const filter = {};
    if (type)
        filter.type = type;
    const docs = await db.collection("endpoints").find(filter).sort({ name: 1 }).toArray();
    let eps = docs.map((d) => stripMongo(d));
    if (q) {
        const lower = q.toLowerCase();
        eps = eps.filter((e) => e.name.toLowerCase().includes(lower) ||
            (e.url || "").toLowerCase().includes(lower) ||
            (e.region || "").toLowerCase().includes(lower));
    }
    return eps.map(secrets_1.maskEndpoint);
}
async function getEndpoint(name) {
    const db = await (0, mongo_1.getDb)();
    const doc = await db.collection("endpoints").findOne({ name });
    return doc ? (0, secrets_1.maskEndpoint)(stripMongo(doc)) : null;
}
async function getEndpointRaw(name) {
    const db = await (0, mongo_1.getDb)();
    const doc = await db.collection("endpoints").findOne({ name });
    return doc ? stripMongo(doc) : null;
}
function validateSingleEndpoint(ep) {
    const editable = (0, endpoints_validation_1.fromEndpointsConfig)({ endpoints: [ep] });
    const v = (0, endpoints_validation_1.validateEndpoints)(editable);
    return v.eps[editable[0]?.id] ? [v.eps[editable[0].id]] : [];
}
async function createEndpoint(ep) {
    const errors = validateSingleEndpoint(ep);
    if (errors.length)
        throw new ValidationError(errors);
    const db = await (0, mongo_1.getDb)();
    const existing = await db.collection("endpoints").findOne({ name: ep.name.trim() });
    if (existing)
        throw new ValidationError([`Endpoint "${ep.name}" already exists.`]);
    const doc = { ...ep, name: ep.name.trim() };
    await db.collection("endpoints").insertOne(doc);
    await bumpVersion(db);
    return (0, secrets_1.maskEndpoint)(doc);
}
async function updateEndpoint(name, ep) {
    const db = await (0, mongo_1.getDb)();
    const stored = await getEndpointRaw(name);
    if (!stored)
        throw new NotFoundError(`Endpoint "${name}" not found`);
    const merged = (0, secrets_1.mergeEndpointSecrets)({ ...ep, name: ep.name.trim() }, stored);
    const errors = validateSingleEndpoint(merged);
    if (errors.length)
        throw new ValidationError(errors);
    if (ep.name.trim() !== name) {
        const clash = await db.collection("endpoints").findOne({ name: ep.name.trim() });
        if (clash)
            throw new ValidationError([`Endpoint "${ep.name}" already exists.`]);
    }
    await db.collection("endpoints").deleteOne({ name });
    await db.collection("endpoints").insertOne(merged);
    await bumpVersion(db);
    return (0, secrets_1.maskEndpoint)(merged);
}
async function deleteEndpoint(name) {
    const db = await (0, mongo_1.getDb)();
    const res = await db.collection("endpoints").deleteOne({ name });
    if (!res.deletedCount)
        throw new NotFoundError(`Endpoint "${name}" not found`);
    await bumpVersion(db);
}
async function endpointsByType() {
    const eps = await listEndpoints();
    const map = {};
    for (const e of eps)
        map[e.name] = e.type;
    return map;
}
async function listEnvironments(q) {
    const db = await (0, mongo_1.getDb)();
    const docs = await db.collection("environments").find({}).sort({ name: 1 }).toArray();
    let envs = docs.map((d) => stripMongo(d));
    if (q) {
        const lower = q.toLowerCase();
        envs = envs.filter((e) => e.name.toLowerCase().includes(lower));
    }
    return envs;
}
async function getEnvironment(name) {
    const db = await (0, mongo_1.getDb)();
    const doc = await db.collection("environments").findOne({ name });
    return doc ? stripMongo(doc) : null;
}
function validateSingleEnvironment(env) {
    const editable = [{ id: "x", name: env.name, prometheus: env.prometheus ?? "", loki: env.loki ?? "", kubernetes: env.kubernetes ?? "", aws: env.aws ?? "" }];
    return Object.values((0, environments_validation_1.validateEnvironments)(editable, {}).envs);
}
async function validateEnvironmentRefs(env) {
    const byType = await endpointsByType();
    const editable = [{ id: "x", name: env.name, prometheus: env.prometheus ?? "", loki: env.loki ?? "", kubernetes: env.kubernetes ?? "", aws: env.aws ?? "" }];
    const v = (0, environments_validation_1.validateEnvironments)(editable, byType);
    return Object.values(v.envs);
}
async function createEnvironment(env) {
    const name = env.name.trim();
    let errors = validateSingleEnvironment({ ...env, name });
    if (!errors.length)
        errors = await validateEnvironmentRefs({ ...env, name });
    if (errors.length)
        throw new ValidationError(errors);
    const db = await (0, mongo_1.getDb)();
    if (await db.collection("environments").findOne({ name })) {
        throw new ValidationError([`Environment "${name}" already exists.`]);
    }
    const doc = { ...env, name };
    await db.collection("environments").insertOne(doc);
    await bumpVersion(db);
    return doc;
}
async function updateEnvironment(name, env) {
    const db = await (0, mongo_1.getDb)();
    if (!(await db.collection("environments").findOne({ name }))) {
        throw new NotFoundError(`Environment "${name}" not found`);
    }
    const newName = env.name.trim();
    let errors = validateSingleEnvironment({ ...env, name: newName });
    if (!errors.length)
        errors = await validateEnvironmentRefs({ ...env, name: newName });
    if (errors.length)
        throw new ValidationError(errors);
    if (newName !== name && (await db.collection("environments").findOne({ name: newName }))) {
        throw new ValidationError([`Environment "${newName}" already exists.`]);
    }
    const doc = { ...env, name: newName };
    await db.collection("environments").deleteOne({ name });
    await db.collection("environments").insertOne(doc);
    await bumpVersion(db);
    return doc;
}
async function deleteEnvironment(name) {
    const db = await (0, mongo_1.getDb)();
    const res = await db.collection("environments").deleteOne({ name });
    if (!res.deletedCount)
        throw new NotFoundError(`Environment "${name}" not found`);
    await bumpVersion(db);
}
async function getRoutingConfig() {
    const db = await (0, mongo_1.getDb)();
    const meta = await db.collection("routing_settings").findOne({ _id: ROUTING_META_ID });
    const rules = await db
        .collection("routing_rules")
        .find({})
        .sort({ order: 1 })
        .toArray();
    return {
        default_slack_webhook_url: meta?.default_slack_webhook_url || "",
        routes: rules.map((r) => {
            const { id, order, ...rule } = stripMongo(r);
            return rule;
        }),
    };
}
async function updateRoutingMeta(defaultUrl) {
    const db = await (0, mongo_1.getDb)();
    await db.collection("routing_settings").updateOne({ _id: ROUTING_META_ID }, { $set: { default_slack_webhook_url: defaultUrl } }, { upsert: true });
    await bumpVersion(db);
}
async function listRoutingRules() {
    const db = await (0, mongo_1.getDb)();
    const rules = await db.collection("routing_rules").find({}).sort({ order: 1 }).toArray();
    return rules.map((r) => stripMongo(r));
}
async function createRoutingRule(rule) {
    const db = await (0, mongo_1.getDb)();
    const count = await db.collection("routing_rules").countDocuments();
    const id = crypto.randomUUID();
    const doc = { ...rule, id, order: count };
    await db.collection("routing_rules").insertOne(doc);
    await bumpVersion(db);
    return doc;
}
async function updateRoutingRule(id, rule) {
    const db = await (0, mongo_1.getDb)();
    const existing = await db.collection("routing_rules").findOne({ id });
    if (!existing)
        throw new NotFoundError(`Rule "${id}" not found`);
    const doc = { ...rule, id, order: existing.order ?? 0 };
    await db.collection("routing_rules").replaceOne({ id }, doc);
    await bumpVersion(db);
    return doc;
}
async function deleteRoutingRule(id) {
    const db = await (0, mongo_1.getDb)();
    const res = await db.collection("routing_rules").deleteOne({ id });
    if (!res.deletedCount)
        throw new NotFoundError(`Rule "${id}" not found`);
    await bumpVersion(db);
}
async function reorderRoutingRules(ids) {
    const db = await (0, mongo_1.getDb)();
    for (let i = 0; i < ids.length; i++) {
        await db.collection("routing_rules").updateOne({ id: ids[i] }, { $set: { order: i } });
    }
    await bumpVersion(db);
}
async function getTimeIntervalsConfig() {
    const db = await (0, mongo_1.getDb)();
    const docs = await db.collection("time_intervals").find({}).sort({ order: 1 }).toArray();
    return {
        time_intervals: docs.map((d) => {
            const { order, ...rest } = stripMongo(d);
            return rest;
        }),
    };
}
async function getTimeIntervalNames() {
    const cfg = await getTimeIntervalsConfig();
    return cfg.time_intervals.map((i) => i.name.trim()).filter(Boolean);
}
async function createTimeInterval(interval) {
    const db = await (0, mongo_1.getDb)();
    const count = await db.collection("time_intervals").countDocuments();
    const doc = { ...interval, order: count };
    await db.collection("time_intervals").insertOne(doc);
    await bumpVersion(db);
    return doc;
}
async function updateTimeInterval(name, interval) {
    const db = await (0, mongo_1.getDb)();
    const existing = await db.collection("time_intervals").findOne({ name });
    if (!existing)
        throw new NotFoundError(`Interval "${name}" not found`);
    const doc = { ...interval, order: existing.order ?? 0 };
    if (interval.name.trim() !== name) {
        await db.collection("time_intervals").deleteOne({ name });
        await db.collection("time_intervals").insertOne(doc);
    }
    else {
        await db.collection("time_intervals").replaceOne({ name }, doc);
    }
    await bumpVersion(db);
    return doc;
}
async function deleteTimeInterval(name) {
    const db = await (0, mongo_1.getDb)();
    const res = await db.collection("time_intervals").deleteOne({ name });
    if (!res.deletedCount)
        throw new NotFoundError(`Interval "${name}" not found`);
    await bumpVersion(db);
}
async function reorderTimeIntervals(names) {
    const db = await (0, mongo_1.getDb)();
    for (let i = 0; i < names.length; i++) {
        await db.collection("time_intervals").updateOne({ name: names[i] }, { $set: { order: i } });
    }
    await bumpVersion(db);
}
async function getSilencesConfig() {
    const db = await (0, mongo_1.getDb)();
    const docs = await db.collection("silences").find({}).toArray();
    const active = [];
    const disabled = [];
    for (const d of docs) {
        const { status, ...rule } = stripMongo(d);
        if (status === "disabled")
            disabled.push(rule);
        else
            active.push(rule);
    }
    return { silences: { active, disabled } };
}
async function listSilences(status) {
    const cfg = await getSilencesConfig();
    if (status === "active")
        return cfg.silences.active;
    if (status === "disabled")
        return cfg.silences.disabled;
    return [...cfg.silences.active, ...cfg.silences.disabled];
}
async function createSilence(rule) {
    const db = await (0, mongo_1.getDb)();
    const id = rule.id || crypto.randomUUID();
    const doc = { ...rule, id, status: "active" };
    await db.collection("silences").insertOne(doc);
    await bumpVersion(db);
    return { ...rule, id };
}
async function updateSilence(id, rule, status = "active") {
    const db = await (0, mongo_1.getDb)();
    const existing = await db.collection("silences").findOne({ id });
    if (!existing)
        throw new NotFoundError(`Silence "${id}" not found`);
    const doc = { ...rule, id, status };
    await db.collection("silences").replaceOne({ id }, doc);
    await bumpVersion(db);
    return rule;
}
async function deleteSilence(id) {
    const db = await (0, mongo_1.getDb)();
    const res = await db.collection("silences").deleteOne({ id });
    if (!res.deletedCount)
        throw new NotFoundError(`Silence "${id}" not found`);
    await bumpVersion(db);
}
async function disableSilence(id) {
    const db = await (0, mongo_1.getDb)();
    const doc = await db.collection("silences").findOne({ id, status: "active" });
    if (!doc)
        throw new NotFoundError(`Silence "${id}" not found in active list`);
    await db.collection("silences").updateOne({ id }, {
        $set: {
            status: "disabled",
            disabled_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
            disabled_reason: "manual",
        },
    });
    await bumpVersion(db);
}
async function enableSilence(id, patch) {
    const db = await (0, mongo_1.getDb)();
    const doc = await db.collection("silences").findOne({ id, status: "disabled" });
    if (!doc)
        throw new NotFoundError(`Silence "${id}" not found in disabled list`);
    const mode = patch?.mode || doc.mode || "permanent";
    const set = { status: "active", mode };
    if (mode === "until")
        set.ends_at = patch?.ends_at || doc.ends_at;
    await db.collection("silences").updateOne({ id }, { $set: set, $unset: { disabled_at: "", disabled_reason: "" } });
    await bumpVersion(db);
}
async function reportSummary(days) {
    const db = await (0, mongo_1.getDb)();
    const now = new Date();
    const start = new Date(now.getTime() - days * 86400000);
    const events = await db
        .collection("alert_events")
        .find({ ts: { $gte: start, $lte: now } })
        .toArray();
    const by_alertname = {};
    const hourly = {};
    let totalCost = 0;
    let totalTokens = 0;
    const cost_by_model = {};
    for (const e of events) {
        const name = e.alertname || "unknown";
        if (!by_alertname[name])
            by_alertname[name] = { rca: 0, incoming: 0, cost_usd: 0 };
        const outcome = e.outcome;
        if (outcome === "rca_success" || outcome === "rca_slack_error")
            by_alertname[name].rca++;
        else if (outcome === "accepted")
            by_alertname[name].incoming++;
        const cost = e.cost_usd || 0;
        by_alertname[name].cost_usd = (by_alertname[name].cost_usd || 0) + cost;
        totalCost += cost;
        totalTokens += e.total_tokens || 0;
        const model = e.model || "unknown";
        cost_by_model[model] = (cost_by_model[model] || 0) + cost;
        if (e.ts) {
            const h = new Date(e.ts).toISOString().slice(0, 13) + ":00Z";
            hourly[h] = (hourly[h] || 0) + 1;
        }
    }
    const timeline = Object.entries(hourly)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([hour, count]) => ({ hour, count }));
    const total = Object.values(by_alertname).reduce((s, v) => s + v.rca + v.incoming, 0);
    return {
        source: "mongo",
        files: total,
        by_alertname,
        timeline,
        totals: { events: events.length, cost_usd: totalCost, total_tokens: totalTokens },
        cost_by_model,
        days,
    };
}
async function recentEvents(opts) {
    const db = await (0, mongo_1.getDb)();
    const now = new Date();
    const start = new Date(now.getTime() - opts.days * 86400000);
    const filter = { ts: { $gte: start, $lte: now } };
    if (opts.alertname)
        filter.alertname = opts.alertname;
    if (opts.outcome)
        filter.outcome = opts.outcome;
    const events = await db
        .collection("alert_events")
        .find(filter)
        .sort({ ts: -1 })
        .skip(opts.skip)
        .limit(opts.limit)
        .toArray();
    return events.map((e) => {
        const { _id, ...rest } = e;
        return { ...rest, _id: _id instanceof mongodb_1.ObjectId ? _id.toString() : _id };
    });
}
function readYamlFile(filePath) {
    if (!filePath || !fs_1.default.existsSync(filePath))
        return null;
    return (0, js_yaml_1.load)(fs_1.default.readFileSync(filePath, "utf-8"));
}
function readJsonFile(filePath) {
    if (!filePath || !fs_1.default.existsSync(filePath))
        return null;
    return JSON.parse(fs_1.default.readFileSync(filePath, "utf-8"));
}
const CONFIG_ROOT = process.env.CONFIG_ROOT || path_1.default.join(process.cwd(), '..', '..', 'config');
async function seedIfEmpty() {
    const db = await (0, mongo_1.getDb)();
    const epCount = await db.collection("endpoints").countDocuments();
    if (epCount > 0)
        return;
    const endpointsPath = process.env.ENDPOINTS_CONFIG_PATH || path_1.default.join(CONFIG_ROOT, "endpoints.yaml");
    const envsPath = process.env.ENVIRONMENTS_CONFIG_PATH || path_1.default.join(CONFIG_ROOT, "environments.yaml");
    const routingPath = process.env.ROUTING_CONFIG_PATH || path_1.default.join(CONFIG_ROOT, "routing.yaml");
    const silencesPath = process.env.SILENCES_CONFIG_PATH || path_1.default.join(CONFIG_ROOT, "silences.yaml");
    const intervalsPath = process.env.TIME_INTERVALS_CONFIG_PATH || path_1.default.join(CONFIG_ROOT, "time_intervals.yaml");
    const agentPath = process.env.CONFIG_STORE_PATH || path_1.default.join(CONFIG_ROOT, "web_config.json");
    const epData = readYamlFile(endpointsPath);
    if (epData?.endpoints?.length) {
        await db.collection("endpoints").insertMany(epData.endpoints.map((e) => ({ ...e })));
    }
    const envData = readYamlFile(envsPath);
    if (envData?.environments?.length) {
        await db.collection("environments").insertMany(envData.environments.map((e) => ({ ...e })));
    }
    const routingData = readYamlFile(routingPath);
    if (routingData) {
        await db.collection("routing_settings").updateOne({ _id: ROUTING_META_ID }, { $set: { default_slack_webhook_url: routingData.default_slack_webhook_url || "" } }, { upsert: true });
        const routes = routingData.routes || [];
        await db.collection("routing_rules").insertMany(routes.map((r, i) => ({ ...r, id: crypto.randomUUID(), order: i })));
    }
    const silencesData = readYamlFile(silencesPath);
    if (silencesData?.silences) {
        const docs = [
            ...silencesData.silences.active.map((r) => ({ ...r, status: "active" })),
            ...silencesData.silences.disabled.map((r) => ({ ...r, status: "disabled" })),
        ];
        if (docs.length)
            await db.collection("silences").insertMany(docs);
    }
    const intervalsData = readYamlFile(intervalsPath);
    if (intervalsData?.time_intervals?.length) {
        await db.collection("time_intervals").insertMany(intervalsData.time_intervals.map((t, i) => ({ ...t, order: i })));
    }
    const agentData = readJsonFile(agentPath);
    if (agentData && Object.keys(agentData).length) {
        await db.collection("agent_settings").updateOne({ _id: RUNTIME_ID }, { $set: agentData }, { upsert: true });
    }
    await bumpVersion(db);
}
class ValidationError extends Error {
    constructor(details) {
        super("Validation failed");
        this.details = details;
    }
}
exports.ValidationError = ValidationError;
class NotFoundError extends Error {
    constructor(message) {
        super(message);
    }
}
exports.NotFoundError = NotFoundError;
async function saveEndpointsBulk(body) {
    const db = await (0, mongo_1.getDb)();
    const stored = await db.collection("endpoints").find({}).toArray();
    const storedMap = new Map(stored.map((d) => [d.name, stripMongo(d)]));
    const merged = body.endpoints.map((ep) => (0, secrets_1.mergeEndpointSecrets)(ep, storedMap.get(ep.name)));
    const v = (0, endpoints_validation_1.validateEndpoints)((0, endpoints_validation_1.fromEndpointsConfig)({ endpoints: merged }));
    if (!v.valid)
        throw new ValidationError(Object.values(v.eps));
    await db.collection("endpoints").deleteMany({});
    if (merged.length)
        await db.collection("endpoints").insertMany(merged);
    await bumpVersion(db);
}
async function saveEnvironmentsBulk(body) {
    const byType = await endpointsByType();
    const editable = body.environments.map((e, i) => ({
        id: `e-${i}`,
        name: e.name,
        prometheus: e.prometheus ?? "",
        loki: e.loki ?? "",
        kubernetes: e.kubernetes ?? "",
        aws: e.aws ?? "",
    }));
    const v = (0, environments_validation_1.validateEnvironments)(editable, byType);
    if (!v.valid)
        throw new ValidationError(Object.values(v.envs));
    const db = await (0, mongo_1.getDb)();
    await db.collection("environments").deleteMany({});
    if (body.environments.length)
        await db.collection("environments").insertMany(body.environments);
    await bumpVersion(db);
}
async function saveRoutingBulk(body) {
    const db = await (0, mongo_1.getDb)();
    await db.collection("routing_settings").updateOne({ _id: ROUTING_META_ID }, { $set: { default_slack_webhook_url: body.default_slack_webhook_url || "" } }, { upsert: true });
    await db.collection("routing_rules").deleteMany({});
    const routes = body.routes || [];
    if (routes.length) {
        await db.collection("routing_rules").insertMany(routes.map((r, i) => ({ ...r, id: crypto.randomUUID(), order: i })));
    }
    await bumpVersion(db);
}
async function saveTimeIntervalsBulk(body) {
    const v = (0, time_intervals_validation_1.validateTimeIntervals)(body.time_intervals || []);
    if (!v.valid)
        throw new ValidationError([...v.global, ...Object.values(v.intervals)]);
    const db = await (0, mongo_1.getDb)();
    await db.collection("time_intervals").deleteMany({});
    const intervals = body.time_intervals || [];
    if (intervals.length) {
        await db.collection("time_intervals").insertMany(intervals.map((t, i) => ({ ...t, order: i })));
    }
    await bumpVersion(db);
}
async function saveSilencesBulk(body) {
    if (!body.silences?.active && !body.silences?.disabled) {
        throw new ValidationError(["Invalid silences config"]);
    }
    const db = await (0, mongo_1.getDb)();
    await db.collection("silences").deleteMany({});
    const docs = [
        ...body.silences.active.map((r) => ({ ...r, status: "active" })),
        ...body.silences.disabled.map((r) => ({ ...r, status: "disabled" })),
    ];
    if (docs.length)
        await db.collection("silences").insertMany(docs);
    await bumpVersion(db);
}
//# sourceMappingURL=settings-store.js.map