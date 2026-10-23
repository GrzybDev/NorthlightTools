"""Output and error reporting shared by the commands."""

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from northlighttools.fileio import original_to_keep

console = Console()
error_console = Console(stderr=True)

# Unlike the default, this spinner prints in any console encoding, cp1250 included.
SPINNER = "line"


def reports_errors[**P, R](command: Callable[P, R]) -> Callable[P, R]:
    """Turn the expected failures of a command into a message and exit code 1.

    Args:
        command: The command function to wrap.
    """

    @functools.wraps(command)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return command(*args, **kwargs)
        except (ValueError, OSError) as error:
            error_console.print(f"[bold red]Error:[/] {escape(str(error))}")
            raise typer.Exit(1) from error

    return wrapper


def progress_bar() -> Progress:
    """Return a progress display for the steps of a long command."""
    return Progress(
        SpinnerColumn(SPINNER),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def done(message: str) -> None:
    """Print the outcome of a successful command.

    Args:
        message: What the command did.
    """
    console.print(f"[green]{escape(message)}[/]")


@contextmanager
def reporting_originals(*paths: Path) -> Iterator[None]:
    """Print where the files that the block replaces are kept, once it succeeds.

    Args:
        paths: The files the block writes.
    """
    originals = [original for path in paths if (original := original_to_keep(path))]
    yield
    for original in originals:
        console.print(f"Kept the original as {escape(str(original))}")


def warn(message: str) -> None:
    """Print a warning to the standard error.

    Args:
        message: The warning's text.
    """
    error_console.print(f"[yellow]Warning:[/] {escape(message)}")
