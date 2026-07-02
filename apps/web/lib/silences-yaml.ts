import { dump } from "js-yaml";
import type { SilencesConfig } from "@/lib/types";

export function toSilencesYaml(config: SilencesConfig): string {
  return dump(config, {
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  });
}
