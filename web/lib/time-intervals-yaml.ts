import { dump } from "js-yaml";
import type { TimeIntervalsConfig } from "@/lib/types";

export function toTimeIntervalsYaml(config: TimeIntervalsConfig): string {
  return dump(config, {
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  });
}
