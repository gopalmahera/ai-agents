"""Redis connection and helper wrappers.

Key schema
----------
dedup:<fingerprint>          STRING  "1"   TTL = DEDUP_TTL_SECONDS
counter:<name>                 STRING  int   persistent counters (INCR)
alertname:counts             HASH    alertname → received count
stream:alerts                STREAM  one entry per accepted alert event
"""
import json
import os

import redis

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client: redis.Redis | None = None


def get() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(_REDIS_URL, decode_responses=True)
    return _client


# ── Dedup ────────────────────────────────────────────────────────────────────

def dedup_check_and_set(fingerprint: str, ttl_seconds: int) -> bool:
    """Return True if duplicate (already seen), False + record if new."""
    key = f"dedup:{fingerprint}"
    # SET NX EX is atomic — no lock needed
    was_new = get().set(key, "1", ex=ttl_seconds, nx=True)
    return was_new is None  # None = key existed → duplicate


# ── Counters ─────────────────────────────────────────────────────────────────

def counter_inc(name: str, amount: int = 1) -> None:
    get().incrby(f"counter:{name}", amount)


def counter_get(name: str) -> int:
    val = get().get(f"counter:{name}")
    return int(val) if val else 0


def counter_get_all(names: list[str]) -> dict[str, int]:
    pipe = get().pipeline()
    for name in names:
        pipe.get(f"counter:{name}")
    values = pipe.execute()
    return {name: int(v) if v else 0 for name, v in zip(names, values)}


# ── Per-alertname counts ──────────────────────────────────────────────────────

def alertname_inc(alertname: str, amount: int = 1) -> None:
    get().hincrby("alertname:counts", alertname, amount)


def alertname_counts() -> dict[str, int]:
    raw = get().hgetall("alertname:counts")
    return {k: int(v) for k, v in raw.items()}


# ── Alert event stream ────────────────────────────────────────────────────────

_STREAM_KEY = "stream:alerts"
_STREAM_MAXLEN = 50_000  # keep last 50k events (~months of data for most setups)


def stream_add(
    alertname: str,
    outcome: str,
    namespace: str = "",
    fingerprint: str = "",
    extra: dict | None = None,
) -> None:
    fields = {
        "alertname": alertname,
        "outcome": outcome,
        "namespace": namespace,
        "fingerprint": fingerprint,
        **(extra or {}),
    }
    get().xadd(_STREAM_KEY, fields, maxlen=_STREAM_MAXLEN, approximate=True)


def stream_range(start: str = "-", end: str = "+", count: int = 10_000) -> list[dict]:
    """Return stream entries as list of dicts with added 'ts_ms' field."""
    entries = get().xrange(_STREAM_KEY, start, end, count=count)
    result = []
    for entry_id, fields in entries:
        ts_ms = int(entry_id.split("-")[0])
        result.append({"id": entry_id, "ts_ms": ts_ms, **fields})
    return result


def fingerprint_count_days(fingerprint: str, days: int = 7) -> int:
    """Count accepted alert events for a fingerprint within the last N days."""
    if not fingerprint:
        return 0
    from datetime import datetime, timedelta, timezone

    since_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    entries = stream_range(start=f"{since_ms}-0", count=50_000)
    return sum(
        1
        for entry in entries
        if entry.get("fingerprint") == fingerprint and entry.get("outcome") == "accepted"
    )


def is_available() -> bool:
    try:
        get().ping()
        return True
    except Exception:
        return False


# ── LLM token usage & cost ────────────────────────────────────────────────────
# Cost is stored as integer micro-USD (USD * 1e6) so INCRBY stays integer-safe.

_COST_BY_MODEL = "llm:cost_micro_by_model"
_TOKENS_BY_MODEL = "llm:tokens_by_model"


def record_llm_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_micro_usd: int,
) -> None:
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    total = input_tokens + output_tokens
    cost_micro_usd = cost_micro_usd or 0
    pipe = get().pipeline()
    pipe.incrby("counter:tokens_input", input_tokens)
    pipe.incrby("counter:tokens_output", output_tokens)
    pipe.incrby("counter:tokens_total", total)
    pipe.incrby("counter:cost_micro_usd", cost_micro_usd)
    if model:
        pipe.hincrby(_COST_BY_MODEL, model, cost_micro_usd)
        pipe.hincrby(_TOKENS_BY_MODEL, model, total)
    pipe.execute()


def llm_cost_micro_by_model() -> dict[str, int]:
    return {m: int(v) for m, v in get().hgetall(_COST_BY_MODEL).items()}


def llm_tokens_by_model() -> dict[str, int]:
    return {m: int(v) for m, v in get().hgetall(_TOKENS_BY_MODEL).items()}
