import Redis from "ioredis";

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379/0";

let client: Redis | null = null;

function getRedis(): Redis {
  if (!client) client = new Redis(REDIS_URL, { maxRetriesPerRequest: 1, lazyConnect: true });
  return client;
}

export async function redisHealth(): Promise<boolean> {
  try {
    const r = getRedis();
    if (r.status !== "ready") await r.connect();
    const pong = await r.ping();
    return pong === "PONG";
  } catch {
    return false;
  }
}

const COUNTER_KEYS = [
  "alerts_received",
  "alerts_accepted",
  "alerts_deduplicated",
  "alerts_skipped",
  "alerts_silenced",
  "queue_full",
  "llm_success",
  "llm_fallback",
  "llm_error",
  "slack_success",
  "slack_error",
  "tokens_input",
  "tokens_output",
  "tokens_total",
  "cost_micro_usd",
];

export async function getMetricsStats() {
  const r = getRedis();
  if (r.status !== "ready") await r.connect();
  const pipe = r.pipeline();
  for (const name of COUNTER_KEYS) pipe.get(`counter:${name}`);
  const values = await pipe.exec();
  const counts: Record<string, number> = {};
  COUNTER_KEYS.forEach((name, i) => {
    const val = values?.[i]?.[1];
    counts[name] = val ? parseInt(String(val), 10) : 0;
  });
  const rawAlertnames = await r.hgetall("alertname:counts");
  const by_alertname: Record<string, number> = {};
  for (const [k, v] of Object.entries(rawAlertnames)) {
    by_alertname[k] = parseInt(v, 10);
  }
  let cost_by_model: Record<string, number> = {};
  try {
    const raw = await r.hgetall("llm:cost_micro_by_model");
    for (const [m, micro] of Object.entries(raw)) {
      cost_by_model[m] = Math.round(parseInt(micro, 10) / 1_000_000 * 10000) / 10000;
    }
  } catch {
    cost_by_model = {};
  }
  return {
    alerts_received: counts.alerts_received,
    alerts_accepted: counts.alerts_accepted,
    alerts_deduplicated: counts.alerts_deduplicated,
    alerts_skipped: counts.alerts_skipped,
    alerts_silenced: counts.alerts_silenced,
    queue_full: counts.queue_full,
    llm_investigations: {
      success: counts.llm_success,
      fallback: counts.llm_fallback,
      error: counts.llm_error,
    },
    slack_posts: { success: counts.slack_success, error: counts.slack_error },
    llm_usage: {
      input_tokens: counts.tokens_input,
      output_tokens: counts.tokens_output,
      total_tokens: counts.tokens_total,
      cost_usd: Math.round(counts.cost_micro_usd / 1_000_000 * 10000) / 10000,
    },
    cost_by_model,
    by_alertname,
  };
}

export async function streamRange(sinceMs: number, count = 50_000) {
  const r = getRedis();
  if (r.status !== "ready") await r.connect();
  const entries = await r.xrange("stream:alerts", `${sinceMs}-0`, "+", "COUNT", count);
  return entries.map(([id, fields]) => {
    const obj: Record<string, string> = {};
    for (let i = 0; i < fields.length; i += 2) {
      obj[fields[i]] = fields[i + 1];
    }
    return { id, ts_ms: parseInt(id.split("-")[0], 10), ...obj } as { id: string; ts_ms: number; alertname?: string; outcome?: string };
  });
}
