"""Filesystem helpers."""
import os
from pathlib import Path


def atomic_write_text(path: str | os.PathLike, text: str, encoding: str = "utf-8") -> None:
    """Write text to ``path`` atomically.

    Writes to a sibling ``*.tmp`` file and ``os.replace``s it into place, so a
    crash or ENOSPC mid-write never leaves a truncated/torn file — readers see
    either the old contents or the fully-written new contents.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp")
    with open(tmp, "w", encoding=encoding) as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)
