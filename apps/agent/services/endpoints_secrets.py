"""Mask / merge secrets in the dynamic endpoint registry.

The registry is a list of endpoints (matched by ``name``), so the fixed-key
``SENSITIVE_KEYS`` masking used elsewhere doesn't apply. On GET, secret fields
are replaced with ``***``; on POST, a field still equal to ``***`` means
"unchanged" and is restored from the stored endpoint of the same name.
"""

import copy

MASK = "***"

# Secret field paths within each endpoint dict, keyed by endpoint type.
_SECRET_PATHS = {
    "prometheus": (("auth", "password"), ("auth", "token")),
    "loki": (("auth", "password"), ("auth", "token")),
    "kubernetes": (("token",),),
    "aws": (("auth", "secret_access_key"),),
}


def _get(d, path):
    for key in path[:-1]:
        d = d.get(key) if isinstance(d, dict) else None
        if not isinstance(d, dict):
            return None
    return d.get(path[-1]) if isinstance(d, dict) else None


def _set(d, path, value):
    for key in path[:-1]:
        nxt = d.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            d[key] = nxt
        d = nxt
    d[path[-1]] = value


def _del(d, path):
    for key in path[:-1]:
        d = d.get(key) if isinstance(d, dict) else None
        if not isinstance(d, dict):
            return
    if isinstance(d, dict):
        d.pop(path[-1], None)


def _paths(ep: dict):
    return _SECRET_PATHS.get(str(ep.get("type") or "").lower(), ())


def mask_endpoints(body: dict) -> dict:
    """Return a copy of ``body`` with non-empty secret fields replaced by ``***``."""
    body = copy.deepcopy(body or {})
    for ep in body.get("endpoints", []) or []:
        if not isinstance(ep, dict):
            continue
        for path in _paths(ep):
            if _get(ep, path):
                _set(ep, path, MASK)
    return body


def merge_endpoint_secrets(new_body: dict, stored_body: dict) -> dict:
    """Restore ``***`` secrets in ``new_body`` from ``stored_body`` (by name).

    A masked value with no stored counterpart (e.g. a renamed/new endpoint) is
    dropped rather than persisted as the literal ``***``.
    """
    new_body = copy.deepcopy(new_body or {})
    stored_by_name = {
        str(ep.get("name")): ep
        for ep in (stored_body or {}).get("endpoints", []) or []
        if isinstance(ep, dict) and ep.get("name")
    }
    for ep in new_body.get("endpoints", []) or []:
        if not isinstance(ep, dict):
            continue
        stored = stored_by_name.get(str(ep.get("name")))
        for path in _paths(ep):
            if _get(ep, path) == MASK:
                prev = _get(stored, path) if stored else None
                if prev:
                    _set(ep, path, prev)
                else:
                    _del(ep, path)
    return new_body
