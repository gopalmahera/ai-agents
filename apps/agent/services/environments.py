"""Environments → named service endpoints.

An **environment** (e.g. ``prod``, ``sit``) selects one Prometheus, one Loki,
one Kubernetes and optionally one AWS endpoint from a shared, reusable
**endpoint registry** (each endpoint carries its own URL/connection details and
auth). The environment for an alert is chosen by the webhook path it arrives on
(``/webhook/<env>``); bare ``/webhook`` uses the environment named ``default``.

Both the endpoint registry and the environment map load from MongoDB
(written by the Next.js admin API) with a local file fallback.

The resolved endpoints for the alert under investigation are held in a
``ContextVar`` (bound once per investigation) so deep query helpers, the MCP
toolset builder and the direct Prometheus/K8s paths can read them without
threading parameters everywhere.
"""

import base64
import contextvars
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

import config as _cfg
import services.store.settings_store as _settings_store


# ── Endpoint value types ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class HttpAuth:
    """Auth for an HTTP endpoint (Prometheus / Loki)."""

    mode: str = "none"  # none | basic | bearer
    username: str = ""
    password: str = ""
    token: str = ""

    def header_value(self) -> str:
        """Ready-to-use ``Authorization`` header value, or "" when unauthenticated."""
        if self.mode == "bearer" and self.token:
            return f"Bearer {self.token}"
        if self.mode == "basic" and (self.username or self.password):
            raw = f"{self.username}:{self.password}".encode("utf-8")
            return "Basic " + base64.b64encode(raw).decode("ascii")
        return ""


@dataclass(frozen=True)
class HttpEndpoint:
    url: str = ""
    auth: HttpAuth = field(default_factory=HttpAuth)


@dataclass(frozen=True)
class KubeEndpoint:
    """Either a named kube-context (from a mounted kubeconfig) OR explicit
    api-server + token + CA. All empty → in-cluster / default kubeconfig."""

    kube_context: str = ""
    api_server: str = ""
    token: str = ""
    ca_cert: str = ""  # PEM content

    @property
    def explicit(self) -> bool:
        return bool(self.api_server and self.token)


@dataclass(frozen=True)
class AwsEndpoint:
    region: str = ""
    mode: str = "default"  # default | assume_role | keys
    role_arn: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""


@dataclass(frozen=True)
class Endpoints:
    prometheus: HttpEndpoint = field(default_factory=HttpEndpoint)
    loki: HttpEndpoint = field(default_factory=HttpEndpoint)
    kubernetes: KubeEndpoint = field(default_factory=KubeEndpoint)
    aws: AwsEndpoint | None = None

    # Back-compat read-only accessors for direct-path consumers and older tests.
    @property
    def prometheus_url(self) -> str:
        return self.prometheus.url

    @property
    def loki_url(self) -> str:
        return self.loki.url

    @property
    def kube_context(self) -> str:
        return self.kubernetes.kube_context


def _defaults() -> Endpoints:
    """Boot-time fallback: global PROMETHEUS_URL/LOKI_URL, in-cluster K8s, no AWS."""
    return Endpoints(
        prometheus=HttpEndpoint(url=getattr(_cfg, "PROMETHEUS_URL", "")),
        loki=HttpEndpoint(url=getattr(_cfg, "LOKI_URL", "")),
        kubernetes=KubeEndpoint(),
        aws=None,
    )


_current: contextvars.ContextVar[Endpoints] = contextvars.ContextVar("env_endpoints")


# ── Config loading (Redis-first, file fallback, cached) ───────────────────────

_endpoints_index: dict[str, dict] | None = None
_environments_index: dict[str, dict] | None = None


def _load_raw(redis_loader, path: str) -> dict[str, Any]:
    text = None
    try:
        text = redis_loader()
    except Exception:
        text = None
    if not text and path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except Exception:
            text = None
    if not text:
        return {}
    return yaml.safe_load(text) or {}


def _load_endpoints() -> dict[str, dict]:
    global _endpoints_index
    if _endpoints_index is not None:
        return _endpoints_index
    data = {"endpoints": _settings_store.list_endpoints()}
    if not data["endpoints"]:
        path = getattr(_cfg, "ENDPOINTS_CONFIG_PATH", "") or os.getenv("ENDPOINTS_CONFIG_PATH", "")
        data = _load_raw(lambda: None, path)
    index: dict[str, dict] = {}
    for ep in data.get("endpoints", []) or []:
        if isinstance(ep, dict) and ep.get("name"):
            index[str(ep["name"])] = ep
    _endpoints_index = index
    return index


def _load_environments() -> dict[str, dict]:
    global _environments_index
    if _environments_index is not None:
        return _environments_index
    data = {"environments": _settings_store.list_environments()}
    if not data["environments"]:
        path = getattr(_cfg, "ENVIRONMENTS_CONFIG_PATH", "") or os.getenv("ENVIRONMENTS_CONFIG_PATH", "")
        data = _load_raw(lambda: None, path)
    index: dict[str, dict] = {}
    for env in data.get("environments", []) or []:
        if isinstance(env, dict) and env.get("name"):
            index[str(env["name"])] = env
    _environments_index = index
    return index


def reset_cache() -> None:
    """Force a reload of both the endpoint registry and the environment map."""
    global _endpoints_index, _environments_index
    _endpoints_index = None
    _environments_index = None


def endpoint_index() -> dict[str, dict]:
    """Public view of the endpoint registry (name → raw endpoint dict)."""
    return dict(_load_endpoints())


# ── Endpoint resolution ───────────────────────────────────────────────────────

def _http_auth(auth: dict | None) -> HttpAuth:
    auth = auth or {}
    return HttpAuth(
        mode=str(auth.get("mode") or "none").strip().lower(),
        username=str(auth.get("username") or ""),
        password=str(auth.get("password") or ""),
        token=str(auth.get("token") or ""),
    )


def _http_endpoint(ref, endpoints: dict, fallback: HttpEndpoint) -> HttpEndpoint:
    ep = endpoints.get(ref) if ref else None
    if not ep:
        return fallback
    return HttpEndpoint(
        url=str(ep.get("url") or "").strip() or fallback.url,
        auth=_http_auth(ep.get("auth")),
    )


def _kube_endpoint(ref, endpoints: dict, fallback: KubeEndpoint) -> KubeEndpoint:
    ep = endpoints.get(ref) if ref else None
    if not ep:
        return fallback
    return KubeEndpoint(
        kube_context=str(ep.get("kube_context") or ""),
        api_server=str(ep.get("api_server") or ""),
        token=str(ep.get("token") or ""),
        ca_cert=str(ep.get("ca_cert") or ""),
    )


def _aws_endpoint(ref, endpoints: dict) -> AwsEndpoint | None:
    ep = endpoints.get(ref) if ref else None
    if not ep:
        return None
    auth = ep.get("auth") or {}
    return AwsEndpoint(
        region=str(ep.get("region") or ""),
        mode=str(auth.get("mode") or "default").strip().lower(),
        role_arn=str(auth.get("role_arn") or ""),
        access_key_id=str(auth.get("access_key_id") or ""),
        secret_access_key=str(auth.get("secret_access_key") or ""),
    )


def resolve(env_name: str | None) -> Endpoints:
    """Resolve the endpoint set for an environment name.

    ``None`` or an unknown name falls back to the environment literally named
    ``default``; if that is absent too, to the boot-time defaults. Each endpoint
    ref is looked up in the registry; a missing ref falls back per-source.
    """
    base = _defaults()
    environments = _load_environments()

    env = environments.get((env_name or "").strip()) if env_name else None
    if env is None:
        env = environments.get("default")
    if env is None:
        return base

    endpoints = _load_endpoints()
    return Endpoints(
        prometheus=_http_endpoint(env.get("prometheus"), endpoints, base.prometheus),
        loki=_http_endpoint(env.get("loki"), endpoints, base.loki),
        kubernetes=_kube_endpoint(env.get("kubernetes"), endpoints, base.kubernetes),
        aws=_aws_endpoint(env.get("aws"), endpoints),
    )


# ── Per-investigation binding ─────────────────────────────────────────────────

def bind(env_name: str | None) -> contextvars.Token:
    """Resolve endpoints for this alert's environment and bind them."""
    return _current.set(resolve(env_name))


def reset(token: contextvars.Token) -> None:
    try:
        _current.reset(token)
    except Exception:
        pass


def current() -> Endpoints:
    """Endpoints for the alert under investigation, or global defaults."""
    return _current.get(None) or _defaults()
