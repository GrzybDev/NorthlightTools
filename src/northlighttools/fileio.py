"""File writing that never leaves a half-written file behind."""

import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


@contextmanager
def atomic_writer(path: Path) -> Iterator[BinaryIO]:
    """Open a temporary file that replaces path only when the block succeeds.

    Args:
        path: File to create or replace.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "wb") as stream:
            # mkstemp makes files only their owner can read; keep the usual ones.
            Path(temporary).chmod(_mode(path))
            yield stream
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_atomically(path: Path, data: bytes) -> None:
    """Write data to path through a temporary file.

    Args:
        path: File to create or replace.
        data: The file's new contents.
    """
    with atomic_writer(path) as stream:
        stream.write(data)


def _mode(path: Path) -> int:
    """Return the permissions of the file being replaced, or those of a new file."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask
