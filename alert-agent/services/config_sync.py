"""Background config sync — keeps every replica aligned with the shared store.

Each agent process runs one daemon thread that:
1. Seeds Redis from web_config.json on first boot (migration path)
2. Applies the stored config once at startup
3. Listens on the ``config:events`` pub/sub channel and re-applies the
   shared config whenever any replica saves a change
4. Double-checks ``config:version`` every POLL_SECONDS to cover pub/sub
   messages missed during reconnects

Redis being down never crashes the agent — the thread retries with
backoff and the process keeps running on env/file config.
"""
import json
import threading
import time

import services.store.redis_client as _redis
from services import config_store

POLL_SECONDS = 30
RETRY_SECONDS = 5

_applied_version = -1
_started = False


def _apply(version: int) -> None:
    global _applied_version
    config_store.apply_stored()
    _reset_routing_cache()
    _applied_version = version
    print(f"[config_sync] Applied shared config (version {version})")


def _reset_routing_cache() -> None:
    try:
        from services.notification import routing
        routing.reset_cache()
    except Exception:
        pass


def _apply_if_newer(force: bool = False) -> None:
    version = _redis.config_version()
    if force or version != _applied_version:
        _apply(version)


def _run() -> None:
    pubsub = None
    last_check = 0.0
    while True:
        try:
            if pubsub is None:
                config_store.seed_redis_from_file()
                pubsub = _redis.subscribe_events()
                _apply_if_newer(force=True)
                last_check = time.monotonic()

            message = pubsub.get_message(timeout=POLL_SECONDS)
            if message and message.get("type") == "message":
                data = json.loads(message["data"])
                _apply(int(data.get("version", 0)))
                last_check = time.monotonic()

            if time.monotonic() - last_check >= POLL_SECONDS:
                _apply_if_newer()
                last_check = time.monotonic()
        except Exception as exc:
            print(f"[config_sync] Sync error: {exc} — retrying in {RETRY_SECONDS}s")
            try:
                if pubsub is not None:
                    pubsub.close()
            except Exception:
                pass
            pubsub = None
            time.sleep(RETRY_SECONDS)


def start() -> None:
    """Start the sync thread (idempotent, safe without Redis)."""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_run, name="config-sync", daemon=True).start()
