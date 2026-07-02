export declare class MetricsController {
    stats(): Promise<{
        alerts_received: number;
        alerts_accepted: number;
        alerts_deduplicated: number;
        alerts_skipped: number;
        alerts_silenced: number;
        queue_full: number;
        llm_investigations: {
            success: number;
            fallback: number;
            error: number;
        };
        slack_posts: {
            success: number;
            error: number;
        };
        llm_usage: {
            input_tokens: number;
            output_tokens: number;
            total_tokens: number;
            cost_usd: number;
        };
        cost_by_model: Record<string, number>;
        by_alertname: Record<string, number>;
    }>;
    stream(sinceMs?: string, count?: string): Promise<{
        entries: {
            id: string;
            ts_ms: number;
            alertname?: string;
            outcome?: string;
        }[];
    }>;
}
