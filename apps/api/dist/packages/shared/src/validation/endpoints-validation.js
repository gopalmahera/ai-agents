"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ENDPOINT_TYPES = void 0;
exports.blankEndpoint = blankEndpoint;
exports.toEndpointsConfig = toEndpointsConfig;
exports.fromEndpointsConfig = fromEndpointsConfig;
exports.validateEndpoints = validateEndpoints;
exports.endpointsByType = endpointsByType;
exports.ENDPOINT_TYPES = [
    { value: "prometheus", label: "Prometheus" },
    { value: "loki", label: "Loki" },
    { value: "kubernetes", label: "Kubernetes" },
    { value: "aws", label: "AWS (Cloud)" },
];
function blankEndpoint(type, id) {
    return {
        id,
        name: "",
        type,
        url: "",
        http_auth_mode: "none",
        username: "",
        password: "",
        bearer_token: "",
        kube_context: "",
        api_server: "",
        kube_token: "",
        ca_cert: "",
        region: "",
        aws_auth_mode: "default",
        role_arn: "",
        access_key_id: "",
        secret_access_key: "",
    };
}
function isHttpUrl(u) {
    const t = u.trim();
    if (!t)
        return false;
    try {
        const p = new URL(t);
        return p.protocol === "http:" || p.protocol === "https:";
    }
    catch {
        return false;
    }
}
function toEndpointsConfig(eps) {
    return {
        endpoints: eps.map((e) => {
            const out = { name: e.name.trim(), type: e.type };
            if (e.type === "prometheus" || e.type === "loki") {
                out.url = e.url.trim();
                const mode = e.http_auth_mode || "none";
                out.auth = { mode };
                if (mode === "basic") {
                    out.auth.username = e.username;
                    out.auth.password = e.password;
                }
                else if (mode === "bearer") {
                    out.auth.token = e.bearer_token;
                }
            }
            else if (e.type === "kubernetes") {
                if (e.kube_context.trim())
                    out.kube_context = e.kube_context.trim();
                if (e.api_server.trim())
                    out.api_server = e.api_server.trim();
                if (e.kube_token)
                    out.token = e.kube_token;
                if (e.ca_cert.trim())
                    out.ca_cert = e.ca_cert;
            }
            else if (e.type === "aws") {
                if (e.region.trim())
                    out.region = e.region.trim();
                const mode = e.aws_auth_mode || "default";
                out.auth = { mode };
                if (mode === "assume_role") {
                    out.auth.role_arn = e.role_arn;
                }
                else if (mode === "keys") {
                    out.auth.access_key_id = e.access_key_id;
                    out.auth.secret_access_key = e.secret_access_key;
                }
            }
            return out;
        }),
    };
}
function fromEndpointsConfig(cfg) {
    return (cfg?.endpoints ?? []).map((e, i) => ({
        id: `ep-${i}-${e.name ?? ""}`,
        name: e.name ?? "",
        type: (e.type ?? "prometheus"),
        url: e.url ?? "",
        http_auth_mode: e.auth?.mode ?? "none",
        username: e.auth?.username ?? "",
        password: e.auth?.password ?? "",
        bearer_token: e.auth?.token ?? "",
        kube_context: e.kube_context ?? "",
        api_server: e.api_server ?? "",
        kube_token: e.token ?? "",
        ca_cert: e.ca_cert ?? "",
        region: e.region ?? "",
        aws_auth_mode: e.auth?.mode ?? "default",
        role_arn: e.auth?.role_arn ?? "",
        access_key_id: e.auth?.access_key_id ?? "",
        secret_access_key: e.auth?.secret_access_key ?? "",
    }));
}
function validateEndpoints(eps) {
    const result = { valid: true, eps: {} };
    const seen = new Set();
    for (const e of eps) {
        let err = "";
        const name = e.name.trim();
        if (!name)
            err = "Name is required.";
        else if (seen.has(name))
            err = `Duplicate name "${name}".`;
        else
            seen.add(name);
        if (e.type === "prometheus" || e.type === "loki") {
            if (!isHttpUrl(e.url))
                err = err || "URL must be an http(s) URL.";
            if (e.http_auth_mode === "basic" && !e.username.trim())
                err = err || "Basic auth requires a username.";
            if (e.http_auth_mode === "bearer" && !e.bearer_token.trim())
                err = err || "Bearer auth requires a token.";
        }
        else if (e.type === "kubernetes") {
            if (!e.kube_context.trim() && !e.api_server.trim()) {
                err = err || "Set a kube-context, or api-server + token (or leave empty for in-cluster).";
            }
            if (e.api_server.trim()) {
                if (!isHttpUrl(e.api_server))
                    err = err || "API server must be an http(s) URL.";
                if (!e.kube_token.trim())
                    err = err || "API server requires a token.";
            }
        }
        else if (e.type === "aws") {
            if (e.aws_auth_mode === "assume_role" && !e.role_arn.trim())
                err = err || "Assume-role requires a role ARN.";
            if (e.aws_auth_mode === "keys" && !(e.access_key_id.trim() && e.secret_access_key.trim())) {
                err = err || "Keys mode requires an access key ID and secret.";
            }
        }
        if (err) {
            result.valid = false;
            result.eps[e.id] = err;
        }
    }
    return result;
}
function endpointsByType(eps) {
    const map = {};
    for (const e of eps)
        if (e.name.trim())
            map[e.name.trim()] = e.type;
    return map;
}
//# sourceMappingURL=endpoints-validation.js.map