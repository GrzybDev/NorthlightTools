from pathlib import Path

import typer


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
