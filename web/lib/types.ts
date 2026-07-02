export interface AgentConfig {
  AI_PROVIDER: string;
  OPENAI_MODEL: string;
  OPENAI_MODEL_INFO?: string;
  OPENAI_API_KEY: string;
  OPENAI_BASE_URL?: string;
  ANTHROPIC_API_KEY?: string;
  GEMINI_API_KEY?: string;
  GOOGLE_SA_JSON?: string;
  GOOGLE_CLOUD_PROJECT?: string;
  GOOGLE_CLOUD_LOCATION?: string;
  GOOGLE_GENAI_USE_VERTEXAI?: string;
  AWS_REGION?: string;
  AWS_ROLE_ARN?: string;
  LLM_ENABLED: boolean | string;
  SLACK_WEBHOOK_URL: string;
  PROMETHEUS_URL: string;
  LOKI_URL: string;
  LOGS_DIR: string;
  DEDUP_TTL_SECONDS: number | string;
  ALLOWED_ALERTNAMES: string;
  ALERT_CATALOG_PATH: string;
  ROUTING_CONFIG_PATH: string;
}

export interface McpHealthEntry {
  url: string;
  status: "healthy" | "unreachable" | "error" | "not_configured";
  code?: number;
  error?: string;
}

export type McpHealth = Record<string, McpHealthEntry>;

export interface MetricsStats {
  alerts_received: number;
  alerts_accepted: number;
  alerts_deduplicated: number;
  alerts_skipped: number;
  alerts_silenced: number;
  queue_full?: number;
  llm_investigations: { success: number; fallback: number; error: number };
  slack_posts: { success: number; error: number };
  llm_usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_usd: number;
  };
  cost_by_model?: Record<string, number>;
  by_alertname: Record<string, number>;
}

export interface ReportSummary {
  source?: "mongo" | "redis";
  files: number;
  by_alertname: Record<string, { rca: number; incoming: number; cost_usd?: number }>;
  timeline: { hour: string; count: number }[];
  totals?: { events: number; cost_usd: number; total_tokens: number };
  cost_by_model?: Record<string, number>;
  days?: number;
}

export interface LogEntry {
  name: string;
  type: "rca" | "incoming";
  alertname: string;
  timestamp: string;
  size: number;
}

export interface RoutingConfig {
  default_slack_webhook_url?: string;
  routes: RoutingRule[];
}

export interface RoutingRule {
  match?: Record<string, string>;
  match_re?: Record<string, string>;
  slack_webhook_url: string;
  mute_time_intervals?: string[];
}

export type EndpointType = "prometheus" | "loki" | "kubernetes" | "aws";

export interface EndpointAuth {
  mode?: string; // http: none|basic|bearer ; aws: default|assume_role|keys
  username?: string;
  password?: string;
  token?: string; // http bearer token
  role_arn?: string;
  access_key_id?: string;
  secret_access_key?: string;
}

export interface Endpoint {
  name: string;
  type: EndpointType;
  // prometheus / loki
  url?: string;
  // kubernetes
  kube_context?: string;
  api_server?: string;
  token?: string;
  ca_cert?: string;
  // aws
  region?: string;
  auth?: EndpointAuth;
}

export interface EndpointsConfig {
  endpoints: Endpoint[];
}

export interface Environment {
  name: string;
  prometheus?: string;
  loki?: string;
  kubernetes?: string;
  aws?: string;
}

export interface EnvironmentsConfig {
  environments: Environment[];
}

export interface TimeSlot {
  start_time: string;
  end_time: string;
}

export interface TimeSubInterval {
  weekdays?: string[];
  times?: TimeSlot[];
  location?: string;
}

export interface NamedTimeInterval {
  name: string;
  time_intervals: TimeSubInterval[];
}

export type SilenceMode = "permanent" | "until";

export interface SilenceRule {
  id: string;
  comment?: string;
  created_at?: string;
  mode: SilenceMode;
  ends_at?: string;
  match?: Record<string, string>;
  match_re?: Record<string, string>;
  disabled_at?: string;
  disabled_reason?: "expired" | "manual";
}

export interface SilencesConfig {
  silences: {
    active: SilenceRule[];
    disabled: SilenceRule[];
  };
}

export interface TimeIntervalsConfig {
  time_intervals: NamedTimeInterval[];
}
