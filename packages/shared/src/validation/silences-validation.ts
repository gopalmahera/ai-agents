import type { LabelCondition } from "@shared/validation/routing-validation";
import type { SilenceMode, SilenceRule, SilencesConfig } from "@shared/types";

export type EditableSilence = {
  id: string;
  comment: string;
  mode: SilenceMode;
  ends_at: string;
  conditions: LabelCondition[];
};

export type SilencesValidation = {
  valid: boolean;
  global: string[];
  silences: Record<string, { general?: string; conditions: Record<number, string> }>;
};

function isValidRegex(pattern: string): boolean {
  try {
    // eslint-disable-next-line no-new
    new RegExp(pattern);
    return true;
  } catch {
    return false;
  }
}

export function silenceToConditions(rule: SilenceRule): LabelCondition[] {
  const conditions: LabelCondition[] = [];
  for (const [key, value] of Object.entries(rule.match ?? {})) {
    conditions.push({ key, kind: "exact", value });
  }
  for (const [key, value] of Object.entries(rule.match_re ?? {})) {
    conditions.push({ key, kind: "regex", value });
  }
  return conditions.length ? conditions : [{ key: "", kind: "exact", value: "" }];
}

export function conditionsToSilenceMatchers(conditions: LabelCondition[]) {
  const match: Record<string, string> = {};
  const match_re: Record<string, string> = {};
  for (const c of conditions) {
    const key = c.key.trim();
    if (!key) continue;
    if (c.kind === "exact") match[key] = c.value;
    else match_re[key] = c.value;
  }
  return {
    ...(Object.keys(match).length ? { match } : {}),
    ...(Object.keys(match_re).length ? { match_re } : {}),
  };
}

export function editableToSilenceRule(editable: EditableSilence): SilenceRule {
  return {
    id: editable.id,
    comment: editable.comment.trim() || undefined,
    created_at: new Date().toISOString(),
    mode: editable.mode,
    ...(editable.mode === "until" ? { ends_at: editable.ends_at } : {}),
    ...conditionsToSilenceMatchers(editable.conditions),
  };
}

export function validateSilencesConfig(activeSilences: EditableSilence[]): SilencesValidation {
  const result: SilencesValidation = { valid: true, global: [], silences: {} };

  activeSilences.forEach((silence, index) => {
    const errors: { general?: string; conditions: Record<number, string> } = {
      conditions: {},
    };
    const keyed = silence.conditions.filter((c) => c.key.trim());
    if (!keyed.length) {
      errors.general = "Add at least one label matcher.";
    }
    silence.conditions.forEach((c, ci) => {
      if (!c.key.trim() && !c.value.trim()) return;
      if (!c.key.trim()) errors.conditions[ci] = "Label key required.";
      else if (!c.value.trim()) errors.conditions[ci] = "Value required.";
      else if (c.kind === "regex" && !isValidRegex(c.value)) {
        errors.conditions[ci] = "Invalid regex.";
      }
    });
    if (silence.mode === "until" && !silence.ends_at.trim()) {
      errors.general = "End date/time is required for until mode.";
    }
    const hasErrors = Boolean(errors.general) || Object.keys(errors.conditions).length > 0;
    if (hasErrors) {
      result.valid = false;
      result.silences[silence.id] = errors;
      result.global.push(`Active silence ${index + 1} has errors.`);
    }
  });

  return result;
}

export function buildSilencesConfig(
  activeSilences: EditableSilence[],
  disabled: SilenceRule[],
): SilencesConfig {
  return {
    silences: {
      active: activeSilences.map(editableToSilenceRule),
      disabled,
    },
  };
}
