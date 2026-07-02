import { dump } from "js-yaml";
import type { RoutingConfig, RoutingRule } from "@/lib/types";

function normalizeRoute(route: RoutingRule): Record<string, unknown> {
  const out: Record<string, unknown> = {
    slack_webhook_url: route.slack_webhook_url,
  };
  if (route.match && Object.keys(route.match).length > 0) {
    out.match = route.match;
  }
  if (route.match_re && Object.keys(route.match_re).length > 0) {
    out.match_re = route.match_re;
  }
  if (route.mute_time_intervals && route.mute_time_intervals.length > 0) {
    out.mute_time_intervals = route.mute_time_intervals;
  }
  return out;
}

/** Serialize routing config to YAML (matches backend PyYAML safe_dump output). */
export function toRoutingYaml(config: RoutingConfig): string {
  const doc = {
    default_slack_webhook_url: config.default_slack_webhook_url ?? "",
    routes: config.routes.map(normalizeRoute),
  };

  return dump(doc, {
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  });
}
