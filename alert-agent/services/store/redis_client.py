"""Redis connection and helper wrappers.

Key schema
----------
dedup:<fingerprint>          STRING  "1"   TTL = DEDUP_TTL_SECONDS
counter:<name>               STRING  int   persistent counters (INCR)
alertname:counts             HASH    alertname → received count
stream:alerts                STREAM  one entry per accepted alert event
config:store                 HASH    key → JSON value (shared runtime config)
config:version               STRING  int, bumped on every config change
config:routing_yaml          STRING  routing rules as YAML text
config:silences_yaml         STRING  silences as YAML text
config:time_intervals_yaml STRING  named time intervals as YAML text
config:mute_yaml             STRING  legacy combined mute config (migration only)
config:events                PUBSUB  {"kind": "config"|"routing"|"silences"|"time_intervals", "version": N}
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


# ── Shared config store (synced across replicas) ──────────────────────────────

_CONFIG_HASH = "config:store"
_CONFIG_VERSION_KEY = "config:version"
_ROUTING_YAML_KEY = "config:routing_yaml"
_SILENCES_YAML_KEY = "config:silences_yaml"
_TIME_INTERVALS_YAML_KEY = "config:time_intervals_yaml"
_MUTE_YAML_KEY = "config:mute_yaml"  # legacy — read-only migration
EVENTS_CHANNEL = "config:events"


def config_load() -> dict[str, str]:
    """Raw stored config values (JSON-encoded strings)."""
    return get().hgetall(_CONFIG_HASH)


def config_save(values: dict[str, str]) -> None:
    if values:
        get().hset(_CONFIG_HASH, mapping=values)


def config_save_and_publish(values: dict[str, str]) -> int:
    """Atomically HSET config values and bump the version, then publish.

    The HSET + INCR run in one pipeline so the version always reflects the
    stored values (fixes the SET-succeeds/INCR-fails split). The PUBLISH is a
    best-effort notification; the 30s version poll is the backstop if it drops.
    """
    pipe = get().pipeline()
    if values:
        pipe.hset(_CONFIG_HASH, mapping=values)
    pipe.incr(_CONFIG_VERSION_KEY)
    results = pipe.execute()
    version = int(results[-1])
    get().publish(EVENTS_CHANNEL, json.dumps({"kind": "config", "version": version}))
    return version


def config_is_empty() -> bool:
    return get().hlen(_CONFIG_HASH) == 0


def config_version() -> int:
    val = get().get(_CONFIG_VERSION_KEY)
    return int(val) if val else 0


def publish_config_event(kind: str) -> int:
    """Bump the shared version and notify all replicas. Returns the new version."""
    version = get().incr(_CONFIG_VERSION_KEY)
    get().publish(EVENTS_CHANNEL, json.dumps({"kind": kind, "version": version}))
    return version


def subscribe_events():
    pubsub = get().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(EVENTS_CHANNEL)
    return pubsub


_YAML_KEYS = {
    "routing": _ROUTING_YAML_KEY,
    "silences": _SILENCES_YAML_KEY,
    "time_intervals": _TIME_INTERVALS_YAML_KEY,
}


def save_yaml_and_publish(kind: str, yaml_text: str) -> int:
    """Atomically SET the YAML for ``kind`` and bump the version, then publish.

    SET + INCR share one pipeline so the version always reflects the stored
    YAML. Returns the new version. Raises if ``kind`` is unknown.
    """
    key = _YAML_KEYS[kind]
    pipe = get().pipeline()
    pipe.set(key, yaml_text)
    pipe.incr(_CONFIG_VERSION_KEY)
    results = pipe.execute()
    version = int(results[-1])
    get().publish(EVENTS_CHANNEL, json.dumps({"kind": kind, "version": version}))
    return version


def yaml_is_empty(kind: str) -> bool:
    return not get().get(_YAML_KEYS[kind])


def routing_yaml_load() -> str | None:
    return get().get(_ROUTING_YAML_KEY)


def routing_yaml_save(yaml_text: str) -> None:
    get().set(_ROUTING_YAML_KEY, yaml_text)


def silences_yaml_load() -> str | None:
    return get().get(_SILENCES_YAML_KEY)


def silences_yaml_save(yaml_text: str) -> None:
    get().set(_SILENCES_YAML_KEY, yaml_text)


def time_intervals_yaml_load() -> str | None:
    return get().get(_TIME_INTERVALS_YAML_KEY)


def time_intervals_yaml_save(yaml_text: str) -> None:
    get().set(_TIME_INTERVALS_YAML_KEY, yaml_text)


def mute_yaml_load() -> str | None:
    """Legacy combined config — used only for one-time migration."""
    return get().get(_MUTE_YAML_KEY)
