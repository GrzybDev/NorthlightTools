import typer

from northlighttools.cli import binfnt, rmdp, string_table

app = typer.Typer(
    help="Tools for the files of games made on Remedy's Northlight engine.",
    no_args_is_help=True,
)
app.add_typer(rmdp.app, name="rmdp")
app.add_typer(string_table.app, name="string-table")
app.add_typer(binfnt.app, name="binfnt")
