import typer

from northlighttools import binfnt, rmdp, string_table

app = typer.Typer()
app.add_typer(rmdp.app, name="rmdp")
app.add_typer(binfnt.app, name="binfnt")
app.add_typer(string_table.app, name="string_table")


if __name__ == "__main__":
    app()
