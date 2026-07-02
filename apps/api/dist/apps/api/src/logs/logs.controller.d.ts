export declare class LogsController {
    list(q?: string, type?: string, limit?: string): {
        name: string;
        type: "rca" | "incoming";
        alertname: string;
        timestamp: string;
        size: number;
    }[];
    get(filename: string): {
        filename: string;
        content: string;
    };
    remove(filename: string): {
        ok: boolean;
    };
}
