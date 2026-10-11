import typer

from northlighttools import binfnt, string_table
from northlighttools.cli import rmdp

app = typer.Typer(
    help="Tools for the files of games made on Remedy's Northlight engine.",
    no_args_is_help=True,
)
app.add_typer(rmdp.app, name="rmdp")
app.add_typer(
    string_table.app,
    name="string-table",
    help="Tools for string tables in Remedy games (string_table.bin files)",
)
app.add_typer(
    binfnt.app, name="binfnt", help="Tools for .binfnt files (Binary font files)"
)
