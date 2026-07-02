"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.toEnvConfig = toEnvConfig;
exports.fromEnvConfig = fromEnvConfig;
exports.validateEnvironments = validateEnvironments;
const NAME_RE = /^[A-Za-z0-9._-]+$/;
const RESERVED = new Set(["test"]);
const REF_FIELDS = [
    { field: "prometheus", type: "prometheus" },
    { field: "loki", type: "loki" },
    { field: "kubernetes", type: "kubernetes" },
    { field: "aws", type: "aws" },
];
function toEnvConfig(envs) {
    return {
        environments: envs.map((e) => {
            const out = { name: e.name.trim() };
            if (e.prometheus)
                out.prometheus = e.prometheus;
            if (e.loki)
                out.loki = e.loki;
            if (e.kubernetes)
                out.kubernetes = e.kubernetes;
            if (e.aws)
                out.aws = e.aws;
            return out;
        }),
    };
}
function fromEnvConfig(cfg) {
    return (cfg?.environments ?? []).map((e, i) => ({
        id: `env-${i}-${e.name ?? ""}`,
        name: e.name ?? "",
        prometheus: e.prometheus ?? "",
        loki: e.loki ?? "",
        kubernetes: e.kubernetes ?? "",
        aws: e.aws ?? "",
    }));
}
function validateEnvironments(envs, endpointsByType) {
    const result = { valid: true, envs: {} };
    const seen = new Set();
    for (const e of envs) {
        let err = "";
        const name = e.name.trim();
        if (!name)
            err = "Name is required.";
        else if (!NAME_RE.test(name))
            err = "Name may only contain letters, digits, '.', '_' and '-'.";
        else if (RESERVED.has(name))
            err = `"${name}" is reserved.`;
        else if (seen.has(name))
            err = `Duplicate name "${name}".`;
        else
            seen.add(name);
        for (const { field, type } of REF_FIELDS) {
            const ref = String(e[field] ?? "");
            if (!ref)
                continue;
            const actual = endpointsByType[ref];
            if (!actual)
                err = err || `${type} endpoint "${ref}" no longer exists.`;
            else if (actual !== type)
                err = err || `${type} endpoint "${ref}" is a ${actual} endpoint.`;
        }
        if (err) {
            result.valid = false;
            result.envs[e.id] = err;
        }
    }
    return result;
}
//# sourceMappingURL=environments-validation.js.map