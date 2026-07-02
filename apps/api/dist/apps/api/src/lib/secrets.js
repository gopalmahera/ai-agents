"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AGENT_SENSITIVE_KEYS = exports.MASK = void 0;
exports.maskEndpoint = maskEndpoint;
exports.maskEndpoints = maskEndpoints;
exports.mergeEndpointSecrets = mergeEndpointSecrets;
exports.maskAgentSettings = maskAgentSettings;
exports.mergeAgentSecrets = mergeAgentSecrets;
exports.MASK = "***";
const SECRET_PATHS = {
    prometheus: [["auth", "password"], ["auth", "token"]],
    loki: [["auth", "password"], ["auth", "token"]],
    kubernetes: [["token"]],
    aws: [["auth", "secret_access_key"]],
};
function getPath(obj, path) {
    let cur = obj;
    for (const key of path) {
        if (!cur || typeof cur !== "object")
            return undefined;
        cur = cur[key];
    }
    return cur;
}
function setPath(obj, path, value) {
    let cur = obj;
    for (let i = 0; i < path.length - 1; i++) {
        const key = path[i];
        const nxt = cur[key];
        if (!nxt || typeof nxt !== "object") {
            cur[key] = {};
        }
        cur = cur[key];
    }
    cur[path[path.length - 1]] = value;
}
function delPath(obj, path) {
    let cur = obj;
    for (let i = 0; i < path.length - 1; i++) {
        cur = cur?.[path[i]];
        if (!cur)
            return;
    }
    if (cur)
        delete cur[path[path.length - 1]];
}
function pathsFor(ep) {
    return SECRET_PATHS[ep.type] || [];
}
function maskEndpoint(ep) {
    const out = structuredClone(ep);
    for (const path of pathsFor(out)) {
        if (getPath(out, path)) {
            setPath(out, path, exports.MASK);
        }
    }
    return out;
}
function maskEndpoints(config) {
    return { endpoints: (config.endpoints || []).map(maskEndpoint) };
}
function mergeEndpointSecrets(incoming, stored) {
    const out = structuredClone(incoming);
    for (const path of pathsFor(out)) {
        if (getPath(out, path) === exports.MASK) {
            const prev = stored ? getPath(stored, path) : undefined;
            if (prev) {
                setPath(out, path, prev);
            }
            else {
                delPath(out, path);
            }
        }
    }
    return out;
}
exports.AGENT_SENSITIVE_KEYS = new Set([
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_SA_JSON",
    "SLACK_WEBHOOK_URL",
]);
function maskAgentSettings(values) {
    const out = { ...values };
    for (const key of Array.from(exports.AGENT_SENSITIVE_KEYS)) {
        if (out[key])
            out[key] = exports.MASK;
    }
    return out;
}
function mergeAgentSecrets(incoming, stored) {
    const out = { ...incoming };
    for (const key of Array.from(exports.AGENT_SENSITIVE_KEYS)) {
        if (out[key] === exports.MASK && stored[key]) {
            out[key] = stored[key];
        }
        else if (out[key] === exports.MASK) {
            delete out[key];
        }
    }
    return out;
}
//# sourceMappingURL=secrets.js.map