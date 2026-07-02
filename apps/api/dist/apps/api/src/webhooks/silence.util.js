"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isSilenced = isSilenced;
function parseDt(value) {
    if (!value)
        return null;
    let text = value.trim();
    if (text.endsWith('Z'))
        text = text.slice(0, -1) + '+00:00';
    const dt = new Date(text);
    return Number.isNaN(dt.getTime()) ? null : dt;
}
function silenceIsActive(rule, now) {
    const mode = (rule.mode || 'permanent').trim().toLowerCase();
    if (mode === 'permanent')
        return true;
    if (mode === 'until') {
        const endsAt = parseDt(rule.ends_at);
        return endsAt !== null && now < endsAt;
    }
    return false;
}
function matchesLabels(labels, rule) {
    const match = rule.match || {};
    for (const [key, val] of Object.entries(match)) {
        if (labels[key] !== val)
            return false;
    }
    const matchRe = rule.match_re || {};
    for (const [key, pattern] of Object.entries(matchRe)) {
        const labelVal = labels[key] || '';
        try {
            if (!new RegExp(pattern).test(labelVal))
                return false;
        }
        catch {
            return false;
        }
    }
    return true;
}
function isSilenced(labels, activeRules) {
    const now = new Date();
    for (const rule of activeRules) {
        if (!matchesLabels(labels, rule))
            continue;
        if (silenceIsActive(rule, now)) {
            return { silenced: true, silenceId: rule.id };
        }
    }
    return { silenced: false };
}
//# sourceMappingURL=silence.util.js.map