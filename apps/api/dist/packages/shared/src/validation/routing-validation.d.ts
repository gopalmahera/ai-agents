export type LabelCondition = {
    key: string;
    kind: "exact" | "regex";
    value: string;
};
export type EditableRule = {
    id: string;
    conditions: LabelCondition[];
    slack_webhook_url: string;
    mute_time_intervals: string[];
};
export type RuleValidationErrors = {
    general?: string;
    webhook?: string;
    muteIntervals?: string;
    conditions: Record<number, string>;
};
export type RoutingValidation = {
    valid: boolean;
    defaultUrl?: string;
    rules: Record<string, RuleValidationErrors>;
    global: string[];
};
export declare function isValidWebhookUrl(url: string): boolean;
export declare function validateRouting(defaultUrl: string, rules: EditableRule[], knownIntervalNames?: string[]): RoutingValidation;
