"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isValidWebhookUrl = isValidWebhookUrl;
exports.validateRouting = validateRouting;
const SLACK_WEBHOOK_ENV = "${SLACK_WEBHOOK_URL}";
function isValidWebhookUrl(url) {
    const trimmed = url.trim();
    if (!trimmed)
        return false;
    if (trimmed === SLACK_WEBHOOK_ENV)
        return true;
    try {
        const parsed = new URL(trimmed);
        return parsed.protocol === "https:" && parsed.hostname === "hooks.slack.com";
    }
    catch {
        return false;
    }
}
function isValidRegex(pattern) {
    try {
        new RegExp(pattern);
        return true;
    }
    catch {
        return false;
    }
}
function validateRouting(defaultUrl, rules, knownIntervalNames = []) {
    const result = { valid: true, rules: {}, global: [] };
    const trimmedDefault = defaultUrl.trim();
    if (trimmedDefault && !isValidWebhookUrl(trimmedDefault)) {
        result.valid = false;
        result.defaultUrl =
            "Enter a valid Slack webhook (https://hooks.slack.com/services/…) or leave empty to use SLACK_WEBHOOK_URL from the environment.";
    }
    rules.forEach((rule, index) => {
        const ruleErrors = { conditions: {} };
        const ruleNum = index + 1;
        const activeConditions = rule.conditions.filter((c) => c.key.trim() || c.value.trim());
        const keyedConditions = rule.conditions.filter((c) => c.key.trim());
        if (keyedConditions.length === 0) {
            ruleErrors.general = "Add at least one label condition with a key and value.";
        }
        rule.conditions.forEach((condition, ci) => {
            const hasKey = condition.key.trim().length > 0;
            const hasValue = condition.value.trim().length > 0;
            if (!hasKey && !hasValue)
                return;
            if (!hasKey) {
                ruleErrors.conditions[ci] = "Label key is required.";
                return;
            }
            if (!hasValue) {
                ruleErrors.conditions[ci] = "Value is required.";
                return;
            }
            if (condition.kind === "regex" && !isValidRegex(condition.value)) {
                ruleErrors.conditions[ci] = "Invalid regex pattern.";
            }
        });
        const keys = keyedConditions.map((c) => c.key.trim());
        if (keys.length > 0 && new Set(keys).size !== keys.length) {
            ruleErrors.general = "Each label key can only appear once per rule.";
        }
        if (activeConditions.length > 0 && keyedConditions.length === 0) {
            ruleErrors.general = "Complete every condition row or remove empty rows.";
        }
        if (!isValidWebhookUrl(rule.slack_webhook_url)) {
            ruleErrors.webhook =
                "A valid Slack webhook URL is required for each rule.";
        }
        const known = new Set(knownIntervalNames);
        for (const name of rule.mute_time_intervals) {
            if (name && !known.has(name)) {
                ruleErrors.muteIntervals = `Unknown time interval: ${name}`;
            }
        }
        const hasRuleErrors = Boolean(ruleErrors.general) ||
            Boolean(ruleErrors.webhook) ||
            Boolean(ruleErrors.muteIntervals) ||
            Object.keys(ruleErrors.conditions).length > 0;
        if (hasRuleErrors) {
            result.valid = false;
            result.rules[rule.id] = ruleErrors;
            result.global.push(`Rule ${ruleNum} has validation errors.`);
        }
    });
    if (rules.length > 0 && !trimmedDefault) {
    }
    return result;
}
//# sourceMappingURL=routing-validation.js.map