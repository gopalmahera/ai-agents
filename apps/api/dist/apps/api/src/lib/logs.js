"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.logEntry = logEntry;
exports.listLogs = listLogs;
exports.readLog = readLog;
exports.deleteLog = deleteLog;
const fs_1 = require("fs");
const path_1 = require("path");
const LOGS_DIR = process.env.LOGS_DIR || "/app/logs";
const TS_RE = /^(\d{8}T\d{6}Z)/;
const SAFE_NAME_RE = /^[\w.\-]+$/;
function logEntry(f, stat) {
    const name = f.name;
    const tsMatch = name.match(TS_RE);
    const tsStr = tsMatch?.[1] ?? "";
    let iso = "";
    if (tsStr) {
        const y = tsStr.slice(0, 4);
        const mo = tsStr.slice(4, 6);
        const d = tsStr.slice(6, 8);
        const h = tsStr.slice(9, 11);
        const mi = tsStr.slice(11, 13);
        const s = tsStr.slice(13, 15);
        iso = `${y}-${mo}-${d}T${h}:${mi}:${s}Z`;
    }
    let logType = "rca";
    let alertname = "";
    if (name.includes("_incoming_")) {
        logType = "incoming";
        alertname = name.slice(tsStr.length + "_incoming_".length).replace(/\.[^.]+$/, "");
    }
    else {
        const rest = tsStr ? name.slice(tsStr.length + 1) : name;
        alertname = rest.split("_")[0];
    }
    return { name, type: logType, alertname, timestamp: iso, size: stat.size };
}
function listLogs(q = "", type = "", limit = 100) {
    const logsDir = path_1.default.resolve(LOGS_DIR);
    if (!fs_1.default.existsSync(logsDir))
        return [];
    const files = fs_1.default
        .readdirSync(logsDir, { withFileTypes: true })
        .filter((f) => f.isFile())
        .map((f) => ({ f, stat: fs_1.default.statSync(path_1.default.join(logsDir, f.name)) }))
        .sort((a, b) => b.stat.mtimeMs - a.stat.mtimeMs);
    const entries = [];
    for (const { f, stat } of files) {
        const entry = logEntry(f, stat);
        if (q && !entry.alertname.toLowerCase().includes(q) && !f.name.toLowerCase().includes(q))
            continue;
        if (type && entry.type !== type)
            continue;
        entries.push(entry);
        if (entries.length >= limit)
            break;
    }
    return entries;
}
function readLog(filename) {
    if (!SAFE_NAME_RE.test(filename))
        throw new Error("Invalid filename");
    const logFile = path_1.default.join(path_1.default.resolve(LOGS_DIR), filename);
    if (!fs_1.default.existsSync(logFile))
        throw new Error("Not found");
    return fs_1.default.readFileSync(logFile, "utf-8");
}
function deleteLog(filename) {
    if (!SAFE_NAME_RE.test(filename))
        throw new Error("Invalid filename");
    const logFile = path_1.default.join(path_1.default.resolve(LOGS_DIR), filename);
    if (!fs_1.default.existsSync(logFile))
        throw new Error("Not found");
    fs_1.default.unlinkSync(logFile);
}
//# sourceMappingURL=logs.js.map