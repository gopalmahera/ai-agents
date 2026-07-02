import type { SilenceRule } from '@shared/types';

function parseDt(value?: string): Date | null {
  if (!value) return null;
  let text = value.trim();
  if (text.endsWith('Z')) text = text.slice(0, -1) + '+00:00';
  const dt = new Date(text);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function silenceIsActive(rule: SilenceRule, now: Date): boolean {
  const mode = (rule.mode || 'permanent').trim().toLowerCase();
  if (mode === 'permanent') return true;
  if (mode === 'until') {
    const endsAt = parseDt(rule.ends_at);
    return endsAt !== null && now < endsAt;
  }
  return false;
}

function matchesLabels(labels: Record<string, string>, rule: SilenceRule): boolean {
  const match = rule.match || {};
  for (const [key, val] of Object.entries(match)) {
    if (labels[key] !== val) return false;
  }
  const matchRe = rule.match_re || {};
  for (const [key, pattern] of Object.entries(matchRe)) {
    const labelVal = labels[key] || '';
    try {
      if (!new RegExp(pattern).test(labelVal)) return false;
    } catch {
      return false;
    }
  }
  return true;
}

export function isSilenced(
  labels: Record<string, string>,
  activeRules: SilenceRule[],
): { silenced: boolean; silenceId?: string } {
  const now = new Date();
  for (const rule of activeRules) {
    if (!matchesLabels(labels, rule)) continue;
    if (silenceIsActive(rule, now)) {
      return { silenced: true, silenceId: rule.id };
    }
  }
  return { silenced: false };
}
