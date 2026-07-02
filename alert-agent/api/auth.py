"""Simple bearer-token auth for the web API. Skipped if ADMIN_TOKEN is unset."""
from functools import wraps

from flask import jsonify, request

import config as _cfg


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _cfg.ADMIN_TOKEN:
            return fn(*args, **kwargs)
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {_cfg.ADMIN_TOKEN}":
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper
