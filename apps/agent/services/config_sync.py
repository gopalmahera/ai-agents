"""Config sync disabled — settings are pushed from the NestJS API via WebSocket."""

from utils.log import get_logger

logger = get_logger(__name__)
_started = False


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    logger.info("config_sync disabled — settings pushed from API via WebSocket")
