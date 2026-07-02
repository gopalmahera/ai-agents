import type { EnvironmentsConfig, Environment } from "@shared/types";

export type EditableEnv = {
  id: string;
  name: string;
  prometheus: string;
  loki: string;
  kubernetes: string;
  aws: string;
};

const NAME_RE = /^[A-Za-z0-9._-]+$/;
const RESERVED = new Set(["test"]);

const REF_FIELDS: { field: keyof EditableEnv; type: string }[] = [
  { field: "prometheus", type: "prometheus" },
  { field: "loki", type: "loki" },
  { field: "kubernetes", type: "kubernetes" },
  { field: "aws", type: "aws" },
];

/** Build the API payload from editable state. */
export function toEnvConfig(envs: EditableEnv[]): EnvironmentsConfig {
  return {
    environments: envs.map((e) => {
      const out: Environment = { name: e.name.trim() };
      if (e.prometheus) out.prometheus = e.prometheus;
      if (e.loki) out.loki = e.loki;
      if (e.kubernetes) out.kubernetes = e.kubernetes;
      if (e.aws) out.aws = e.aws;
      return out;
    }),
  };
}

/** Convert a loaded API config into editable state. */
export function fromEnvConfig(cfg: EnvironmentsConfig | undefined): EditableEnv[] {
  return (cfg?.environments ?? []).map((e, i) => ({
    id: `env-${i}-${e.name ?? ""}`,
    name: e.name ?? "",
    prometheus: e.prometheus ?? "",
    loki: e.loki ?? "",
    kubernetes: e.kubernetes ?? "",
    aws: e.aws ?? "",
  }));
}

export type EnvValidation = { valid: boolean; envs: Record<string, string> };

/** Validate env names + that each endpoint ref exists and is of the right type. */
export function validateEnvironments(
  envs: EditableEnv[],
  endpointsByType: Record<string, string>
): EnvValidation {
  const result: EnvValidation = { valid: true, envs: {} };
  const seen = new Set<string>();

  for (const e of envs) {
    let err = "";
    const name = e.name.trim();
    if (!name) err = "Name is required.";
    else if (!NAME_RE.test(name)) err = "Name may only contain letters, digits, '.', '_' and '-'.";
    else if (RESERVED.has(name)) err = `"${name}" is reserved.`;
    else if (seen.has(name)) err = `Duplicate name "${name}".`;
    else seen.add(name);

    for (const { field, type } of REF_FIELDS) {
      const ref = String(e[field] ?? "");
      if (!ref) continue;
      const actual = endpointsByType[ref];
      if (!actual) err = err || `${type} endpoint "${ref}" no longer exists.`;
      else if (actual !== type) err = err || `${type} endpoint "${ref}" is a ${actual} endpoint.`;
    }

    if (err) {
      result.valid = false;
      result.envs[e.id] = err;
    }
  }

  return result;
}
