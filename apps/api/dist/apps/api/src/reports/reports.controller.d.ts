export declare class ReportsController {
    summary(days?: string): Promise<{
        source: "mongo";
        files: number;
        by_alertname: Record<string, {
            rca: number;
            incoming: number;
            cost_usd?: number;
        }>;
        timeline: {
            hour: string;
            count: number;
        }[];
        totals: {
            events: number;
            cost_usd: number;
            total_tokens: number;
        };
        cost_by_model: Record<string, number>;
        days: number;
    }>;
    events(days?: string, alertname?: string, outcome?: string, limit?: string, skip?: string): Promise<{
        _id: string;
    }[]>;
}
