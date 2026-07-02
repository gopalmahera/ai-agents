"""Validate the environment map submitted via the Web UI.

Environments no longer match on labels — each names a set of endpoint refs
(one per source) and maps to a webhook path (``/webhook/<name>``). Refs are
checked against the current endpoint registry when it is supplied.
"""

import re
from typing import Any

# Environment names appear in the webhook URL path, so keep them path-safe.
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# Reserved: /webhook/test is the (auth-gated) test route.
_RESERVED_NAMES = {"test"}

# ref field on an environment → endpoint type it must point at.
_REF_TYPES = {
    "prometheus": "prometheus",
    "loki": "loki",
    "kubernetes": "kubernetes",
    "aws": "aws",
}


def validate_environments_body(
    body: dict[str, Any],
    endpoints_by_type: dict[str, str] | None = None,
) -> list[str]:
    """Return a list of human-readable validation errors (empty if valid).

    ``endpoints_by_type`` maps endpoint name → type; when provided, each ref is
    verified to exist and match the expected type.
    """
    errors: list[str] = []

    environments = body.get("environments")
    if environments is None or not isinstance(environments, list):
        errors.append("environments must be a list.")
        return errors

    seen_names: set[str] = set()
    for i, env in enumerate(environments, start=1):
        if not isinstance(env, dict):
            errors.append(f"Environment {i} must be an object.")
            continue

        name = str(env.get("name") or "").strip()
        prefix = f"Environment {i}" + (f" ({name})" if name else "")
        if not name:
            errors.append(f"{prefix}: name is required.")
        elif not _NAME_RE.match(name):
            errors.append(f"{prefix}: name may only contain letters, digits, '.', '_' and '-'.")
        elif name in _RESERVED_NAMES:
            errors.append(f"{prefix}: {name!r} is reserved.")
        elif name in seen_names:
            errors.append(f"{prefix}: duplicate name {name!r}.")
        else:
            seen_names.add(name)

        for ref_field, expected_type in _REF_TYPES.items():
            ref = env.get(ref_field)
            if ref in (None, ""):
                continue
            ref = str(ref)
            if endpoints_by_type is None:
                continue
            actual = endpoints_by_type.get(ref)
            if actual is None:
                errors.append(f"{prefix}: {ref_field} endpoint {ref!r} does not exist.")
            elif actual != expected_type:
                errors.append(
                    f"{prefix}: {ref_field} endpoint {ref!r} is a {actual} endpoint, expected {expected_type}."
                )

    return errors
