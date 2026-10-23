"""File writing that never leaves a half-written file behind or loses a file it replaces."""

import os
import stat
import tempfile
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

ORIGINAL_SUFFIX = ".orig"
"""The suffix of the originals that replacing files keeps."""


@contextmanager
def atomic_writer(path: Path) -> Iterator[BinaryIO]:
    """Open a temporary file that replaces path only when the block succeeds.

    The file it replaces is kept where original_to_keep says.

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
        # Moved aside only once the new data is complete, so a crash leaves both.
        if (original := original_to_keep(path)) is not None:
            path.rename(original)
        try:
            Path(temporary).replace(path)
        except BaseException:
            if original is not None:
                original.rename(path)
            raise
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


def original_to_keep(path: Path) -> Path | None:
    """Return where replacing path keeps the file there, or None if it keeps none.

    The file is kept beside path as <name>.orig, unless an earlier original is kept there.

    Args:
        path: The file to replace.
    """
    original = path.with_name(path.name + ORIGINAL_SUFFIX)
    return original if path.is_file() and not original.exists() else None


@contextmanager
def creating_files(paths: Collection[Path]) -> Iterator[None]:
    """Refuse paths that exist, and remove the ones created when the block fails.

    Args:
        paths: The files the block creates.
    """
    for path in paths:
        if path.exists():
            msg = f"{path} already exists; it is kept and nothing was written"
            raise FileExistsError(msg)
    try:
        yield
    except BaseException:
        for path in paths:
            path.unlink(missing_ok=True)
        raise


def _mode(path: Path) -> int:
    """Return the permissions of the file being replaced, or those of a new file."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask
