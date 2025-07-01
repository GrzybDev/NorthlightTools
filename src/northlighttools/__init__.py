import typer

from northlighttools import rmdp

app = typer.Typer(help="Collection of various tools for Northlight Engine")

app.add_typer(
    rmdp.app, name="rmdp", help="Tools for Remedy Packages (.bin/.rmdp files)"
)

if __name__ == "__main__":
    app()
