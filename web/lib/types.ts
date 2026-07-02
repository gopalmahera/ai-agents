export interface AgentConfig {
  AI_PROVIDER: string;
  OPENAI_MODEL: string;
  OPENAI_API_KEY: string;
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
  llm_investigations: { success: number; fallback: number; error: number };
  slack_posts: { success: number; error: number };
  by_alertname: Record<string, number>;
}

export interface ReportSummary {
  files: number;
  by_alertname: Record<string, { rca: number; incoming: number }>;
  timeline: { hour: string; count: number }[];
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
