import typer

from northlighttools import rmdp

app = typer.Typer()
app.add_typer(rmdp.app, name="rmdp")


if __name__ == "__main__":
    app()
