import type { AgentConfig, Endpoint, Environment, NamedTimeInterval, RoutingConfig, RoutingRule, SilenceRule, SilencesConfig, TimeIntervalsConfig } from "@shared/types";
export declare const CONFIGURABLE_KEYS: readonly ["AI_PROVIDER", "OPENAI_MODEL", "OPENAI_MODEL_INFO", "OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_SA_JSON", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_GENAI_USE_VERTEXAI", "AWS_REGION", "AWS_ROLE_ARN", "LLM_ENABLED", "SLACK_WEBHOOK_URL", "PROMETHEUS_URL", "LOKI_URL", "LOGS_DIR", "DEDUP_TTL_SECONDS", "ALLOWED_ALERTNAMES", "ALERT_CATALOG_PATH", "ROUTING_CONFIG_PATH"];
export declare function getSettingsVersion(): Promise<number>;
export declare function getAgentSettings(masked?: boolean): Promise<Record<string, unknown>>;
export declare function updateAgentSettings(updates: Record<string, unknown>): Promise<Record<string, unknown>>;
export declare function listEndpoints(q?: string, type?: string): Promise<Endpoint[]>;
export declare function getEndpoint(name: string): Promise<Endpoint | null>;
export declare function getEndpointRaw(name: string): Promise<Endpoint | null>;
export declare function createEndpoint(ep: Endpoint): Promise<Endpoint>;
export declare function updateEndpoint(name: string, ep: Endpoint): Promise<Endpoint>;
export declare function deleteEndpoint(name: string): Promise<void>;
export declare function endpointsByType(): Promise<Record<string, string>>;
export declare function listEnvironments(q?: string): Promise<Environment[]>;
export declare function getEnvironment(name: string): Promise<Environment | null>;
export declare function createEnvironment(env: Environment): Promise<Environment>;
export declare function updateEnvironment(name: string, env: Environment): Promise<Environment>;
export declare function deleteEnvironment(name: string): Promise<void>;
export type RoutingRuleDoc = RoutingRule & {
    id: string;
    order: number;
};
export declare function getRoutingConfig(): Promise<RoutingConfig>;
export declare function updateRoutingMeta(defaultUrl: string): Promise<void>;
export declare function listRoutingRules(): Promise<RoutingRuleDoc[]>;
export declare function createRoutingRule(rule: RoutingRule): Promise<RoutingRuleDoc>;
export declare function updateRoutingRule(id: string, rule: RoutingRule): Promise<RoutingRuleDoc>;
export declare function deleteRoutingRule(id: string): Promise<void>;
export declare function reorderRoutingRules(ids: string[]): Promise<void>;
export type TimeIntervalDoc = NamedTimeInterval & {
    order: number;
};
export declare function getTimeIntervalsConfig(): Promise<TimeIntervalsConfig>;
export declare function getTimeIntervalNames(): Promise<string[]>;
export declare function createTimeInterval(interval: NamedTimeInterval): Promise<TimeIntervalDoc>;
export declare function updateTimeInterval(name: string, interval: NamedTimeInterval): Promise<TimeIntervalDoc>;
export declare function deleteTimeInterval(name: string): Promise<void>;
export declare function reorderTimeIntervals(names: string[]): Promise<void>;
export type SilenceDoc = SilenceRule & {
    status: "active" | "disabled";
};
export declare function getSilencesConfig(): Promise<SilencesConfig>;
export declare function listSilences(status?: "active" | "disabled"): Promise<SilenceRule[]>;
export declare function createSilence(rule: SilenceRule): Promise<SilenceRule>;
export declare function updateSilence(id: string, rule: SilenceRule, status?: "active" | "disabled"): Promise<SilenceRule>;
export declare function deleteSilence(id: string): Promise<void>;
export declare function disableSilence(id: string): Promise<void>;
export declare function enableSilence(id: string, patch?: Partial<SilenceRule>): Promise<void>;
export declare function reportSummary(days: number): Promise<{
    source: "mongo";
    files: number;
    by_alertname: Record<string, {
        rca: number;
        incoming: number;
        cost_usd?: number;
    }>;
    timeline: {
        hour: string;
        count: number;
    }[];
    totals: {
        events: number;
        cost_usd: number;
        total_tokens: number;
    };
    cost_by_model: Record<string, number>;
    days: number;
}>;
export declare function recentEvents(opts: {
    days: number;
    alertname?: string;
    outcome?: string;
    limit: number;
    skip: number;
}): Promise<{
    _id: string;
}[]>;
export declare function seedIfEmpty(): Promise<void>;
export declare class ValidationError extends Error {
    details: string[];
    constructor(details: string[]);
}
export declare class NotFoundError extends Error {
    constructor(message: string);
}
export declare function saveEndpointsBulk(body: {
    endpoints: Endpoint[];
}): Promise<void>;
export declare function saveEnvironmentsBulk(body: {
    environments: Environment[];
}): Promise<void>;
export declare function saveRoutingBulk(body: RoutingConfig): Promise<void>;
export declare function saveTimeIntervalsBulk(body: TimeIntervalsConfig): Promise<void>;
export declare function saveSilencesBulk(body: SilencesConfig): Promise<void>;
export type { AgentConfig };
