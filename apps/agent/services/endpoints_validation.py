"""Validate the named endpoint registry submitted via the Web UI.

Secrets are merged in (``***`` → stored value) before this runs, so validation
sees real values. See ``api/config_api.merge_endpoint_secrets``.
"""

from typing import Any
from urllib.parse import urlparse

ENDPOINT_TYPES = ("prometheus", "loki", "kubernetes", "aws")
_HTTP_AUTH_MODES = ("none", "basic", "bearer")
_AWS_AUTH_MODES = ("default", "assume_role", "keys")


def _is_http_url(url: str) -> bool:
    url = (url or "").strip()
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _validate_http(prefix: str, ep: dict, errors: list[str]) -> None:
    if not _is_http_url(str(ep.get("url") or "")):
        errors.append(f"{prefix}: url must be an http(s) URL.")
    auth = ep.get("auth") or {}
    if not isinstance(auth, dict):
        errors.append(f"{prefix}: auth must be an object.")
        return
    mode = str(auth.get("mode") or "none").strip().lower()
    if mode not in _HTTP_AUTH_MODES:
        errors.append(f"{prefix}: auth.mode must be one of {', '.join(_HTTP_AUTH_MODES)}.")
    elif mode == "basic" and not str(auth.get("username") or "").strip():
        errors.append(f"{prefix}: basic auth requires a username.")
    elif mode == "bearer" and not str(auth.get("token") or "").strip():
        errors.append(f"{prefix}: bearer auth requires a token.")


def _validate_kubernetes(prefix: str, ep: dict, errors: list[str]) -> None:
    ctx = str(ep.get("kube_context") or "").strip()
    api_server = str(ep.get("api_server") or "").strip()
    token = str(ep.get("token") or "").strip()
    if not ctx and not api_server:
        errors.append(f"{prefix}: set kube_context, or api_server + token (or leave all empty for in-cluster).")
        return
    if api_server:
        if not _is_http_url(api_server):
            errors.append(f"{prefix}: api_server must be an http(s) URL.")
        if not token:
            errors.append(f"{prefix}: api_server requires a token.")


def _validate_aws(prefix: str, ep: dict, errors: list[str]) -> None:
    auth = ep.get("auth") or {}
    if not isinstance(auth, dict):
        errors.append(f"{prefix}: auth must be an object.")
        return
    mode = str(auth.get("mode") or "default").strip().lower()
    if mode not in _AWS_AUTH_MODES:
        errors.append(f"{prefix}: auth.mode must be one of {', '.join(_AWS_AUTH_MODES)}.")
    elif mode == "assume_role" and not str(auth.get("role_arn") or "").strip():
        errors.append(f"{prefix}: assume_role requires a role_arn.")
    elif mode == "keys" and not (
        str(auth.get("access_key_id") or "").strip() and str(auth.get("secret_access_key") or "").strip()
    ):
        errors.append(f"{prefix}: keys mode requires access_key_id and secret_access_key.")


def validate_endpoints_body(body: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation errors (empty if valid)."""
    errors: list[str] = []

    endpoints = body.get("endpoints")
    if endpoints is None or not isinstance(endpoints, list):
        errors.append("endpoints must be a list.")
        return errors

    seen: set[str] = set()
    for i, ep in enumerate(endpoints, start=1):
        if not isinstance(ep, dict):
            errors.append(f"Endpoint {i} must be an object.")
            continue

        name = str(ep.get("name") or "").strip()
        etype = str(ep.get("type") or "").strip().lower()
        prefix = f"Endpoint {i}" + (f" ({name})" if name else "")

        if not name:
            errors.append(f"{prefix}: name is required.")
        elif name in seen:
            errors.append(f"{prefix}: duplicate name {name!r}.")
        else:
            seen.add(name)

        if etype not in ENDPOINT_TYPES:
            errors.append(f"{prefix}: type must be one of {', '.join(ENDPOINT_TYPES)}.")
            continue

        if etype in ("prometheus", "loki"):
            _validate_http(prefix, ep, errors)
        elif etype == "kubernetes":
            _validate_kubernetes(prefix, ep, errors)
        elif etype == "aws":
            _validate_aws(prefix, ep, errors)

    return errors
