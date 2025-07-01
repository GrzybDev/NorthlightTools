import typer

from northlighttools import binfnt, rmdp, string_table

app = typer.Typer(help="Collection of various tools for Northlight Engine")

app.add_typer(
    binfnt.app, name="binfnt", help="Tools for .binfnt files (Binary font files)"
)

app.add_typer(
    rmdp.app, name="rmdp", help="Tools for Remedy Packages (.bin/.rmdp files)"
)

app.add_typer(
    string_table.app,
    name="string-table",
    help="Tools for string tables in Remedy games (string_table.bin files)",
)

if __name__ == "__main__":
    app()
