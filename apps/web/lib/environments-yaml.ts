import { dump } from "js-yaml";
import type { EnvironmentsConfig, Environment } from "@/lib/types";

function normalizeEnv(env: Environment): Record<string, unknown> {
  const out: Record<string, unknown> = { name: env.name };
  if (env.prometheus) out.prometheus = env.prometheus;
  if (env.loki) out.loki = env.loki;
  if (env.kubernetes) out.kubernetes = env.kubernetes;
  if (env.aws) out.aws = env.aws;
  return out;
}

/** Serialize the environments config to YAML (matches backend PyYAML safe_dump). */
export function toEnvironmentsYaml(config: EnvironmentsConfig): string {
  return dump({ environments: config.environments.map(normalizeEnv) }, {
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  });
}
