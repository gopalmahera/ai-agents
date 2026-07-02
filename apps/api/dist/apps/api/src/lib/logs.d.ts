import fs from "fs";
export declare function logEntry(f: fs.Dirent | {
    name: string;
    isFile: () => boolean;
}, stat: fs.Stats): {
    name: string;
    type: "rca" | "incoming";
    alertname: string;
    timestamp: string;
    size: number;
};
export declare function listLogs(q?: string, type?: string, limit?: number): {
    name: string;
    type: "rca" | "incoming";
    alertname: string;
    timestamp: string;
    size: number;
}[];
export declare function readLog(filename: string): string;
export declare function deleteLog(filename: string): void;
