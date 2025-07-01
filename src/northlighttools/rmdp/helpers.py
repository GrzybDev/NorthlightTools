from datetime import datetime, timezone
from pathlib import Path

import typer

from northlighttools.rmdp.constants import EPOCH_AS_FILETIME, HUNDREDS_OF_NANOSECONDS


def get_archive_paths(
    archive_path: Path,
):
    bin_path = archive_path.with_suffix(".bin")
    rmdp_path = archive_path.with_suffix(".rmdp")

    missing = [str(p) for p in [bin_path, rmdp_path] if not p.exists()]
    if missing:
        raise typer.BadParameter(
            f"Cannot read {archive_path} because the following required file(s) are missing: {', '.join(missing)}"
        )

    return bin_path, rmdp_path


def filetime_to_dt(ft: int) -> datetime:
    # Get seconds and remainder in terms of Unix epoch
    s, ns100 = divmod(ft - EPOCH_AS_FILETIME, HUNDREDS_OF_NANOSECONDS)
    # Convert to datetime object, with remainder as microseconds.
    return datetime.fromtimestamp(s, tz=timezone.utc).replace(microsecond=(ns100 // 10))
