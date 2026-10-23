import os
import stat
from pathlib import Path

import pytest

from northlighttools.fileio import atomic_writer, write_atomically

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")


def test_a_failed_write_keeps_the_old_file(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(b"old")

    with pytest.raises(RuntimeError), atomic_writer(path) as stream:
        stream.write(b"new")
        raise RuntimeError

    assert path.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [path]


def test_a_file_that_cannot_be_replaced_stays_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(b"old")

    # What Windows does when another program holds the file open.
    def locked(self: Path, target: Path) -> Path:
        raise PermissionError(target)

    monkeypatch.setattr(Path, "replace", locked)
    with pytest.raises(PermissionError):
        write_atomically(path, b"new")

    assert path.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [path]


@posix_only
def test_new_files_get_the_usual_permissions(tmp_path: Path) -> None:
    umask = os.umask(0o022)
    try:
        write_atomically(tmp_path / "file.bin", b"data")
    finally:
        os.umask(umask)

    assert stat.S_IMODE((tmp_path / "file.bin").stat().st_mode) == 0o644


@posix_only
def test_replaced_files_keep_their_permissions(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(b"old")
    path.chmod(0o640)

    write_atomically(path, b"new")

    assert stat.S_IMODE(path.stat().st_mode) == 0o640
