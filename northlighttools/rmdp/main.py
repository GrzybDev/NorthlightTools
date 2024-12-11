from pathlib import Path
from typing import Annotated

import typer

from northlighttools.rmdp.extract import extract_rmdp

app = typer.Typer()


@app.command()
def extract(
    rmdp_file: Annotated[
        Path, typer.Argument(exists=True, file_okay=True, readable=True)
    ],
    output_dir: Annotated[Path, typer.Argument(writable=True)] = None,
):
    if rmdp_file.suffix != ".rmdp":
        raise typer.BadParameter(f"{rmdp_file} is not a .rmdp file!")

    # Check if the file have paired .bin file
    bin_file = rmdp_file.with_suffix(".bin")

    if not bin_file.exists():
        raise typer.BadParameter(
            f"Cannot extract {rmdp_file} without paired {bin_file} file!"
        )

    extract_rmdp(bin_file, rmdp_file, output_dir)


if __name__ == "__main__":
    app()
