import typer

from northlighttools import binfnt, rmdp

app = typer.Typer()
app.add_typer(rmdp.app, name="rmdp")
app.add_typer(binfnt.app, name="binfnt")


if __name__ == "__main__":
    app()
