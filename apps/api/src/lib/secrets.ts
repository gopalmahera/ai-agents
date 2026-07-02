import type { Endpoint, EndpointsConfig } from "@shared/types";

export const MASK = "***";

const SECRET_PATHS: Record<string, (keyof Endpoint | string)[][]> = {
  prometheus: [["auth", "password"], ["auth", "token"]],
  loki: [["auth", "password"], ["auth", "token"]],
  kubernetes: [["token"]],
  aws: [["auth", "secret_access_key"]],
};

function getPath(obj: Record<string, unknown>, path: string[]): unknown {
  let cur: unknown = obj;
  for (const key of path) {
    if (!cur || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  return cur;
}

function setPath(obj: Record<string, unknown>, path: string[], value: unknown): void {
  let cur: Record<string, unknown> = obj;
  for (let i = 0; i < path.length - 1; i++) {
    const key = path[i];
    const nxt = cur[key];
    if (!nxt || typeof nxt !== "object") {
      cur[key] = {};
    }
    cur = cur[key] as Record<string, unknown>;
  }
  cur[path[path.length - 1]] = value;
}

function delPath(obj: Record<string, unknown>, path: string[]): void {
  let cur: Record<string, unknown> | undefined = obj;
  for (let i = 0; i < path.length - 1; i++) {
    cur = cur?.[path[i]] as Record<string, unknown> | undefined;
    if (!cur) return;
  }
  if (cur) delete cur[path[path.length - 1]];
}

function pathsFor(ep: Endpoint): string[][] {
  return SECRET_PATHS[ep.type] || [];
}

export function maskEndpoint(ep: Endpoint): Endpoint {
  const out = structuredClone(ep);
  for (const path of pathsFor(out)) {
    if (getPath(out as unknown as Record<string, unknown>, path)) {
      setPath(out as unknown as Record<string, unknown>, path, MASK);
    }
  }
  return out;
}

export function maskEndpoints(config: EndpointsConfig): EndpointsConfig {
  return { endpoints: (config.endpoints || []).map(maskEndpoint) };
}

export function mergeEndpointSecrets(incoming: Endpoint, stored?: Endpoint | null): Endpoint {
  const out = structuredClone(incoming);
  for (const path of pathsFor(out)) {
    if (getPath(out as unknown as Record<string, unknown>, path) === MASK) {
      const prev = stored ? getPath(stored as unknown as Record<string, unknown>, path) : undefined;
      if (prev) {
        setPath(out as unknown as Record<string, unknown>, path, prev);
      } else {
        delPath(out as unknown as Record<string, unknown>, path);
      }
    }
  }
  return out;
}

export const AGENT_SENSITIVE_KEYS = new Set([
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "GEMINI_API_KEY",
  "GOOGLE_SA_JSON",
  "SLACK_WEBHOOK_URL",
]);

export function maskAgentSettings(values: Record<string, unknown>): Record<string, unknown> {
  const out = { ...values };
  for (const key of Array.from(AGENT_SENSITIVE_KEYS)) {
    if (out[key]) out[key] = MASK;
  }
  return out;
}

export function mergeAgentSecrets(
  incoming: Record<string, unknown>,
  stored: Record<string, unknown>
): Record<string, unknown> {
  const out = { ...incoming };
  for (const key of Array.from(AGENT_SENSITIVE_KEYS)) {
    if (out[key] === MASK && stored[key]) {
      out[key] = stored[key];
    } else if (out[key] === MASK) {
      delete out[key];
    }
  }
  return out;
}
