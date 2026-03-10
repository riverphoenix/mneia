from __future__ import annotations

import json
import os
import sys
from enum import Enum
from typing import Any

from rich.console import Console
from rich.table import Table


class OutputMode(Enum):
    RICH = "rich"
    PLAIN = "plain"
    JSON = "json"


def _detect_no_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return True
    if os.environ.get("TERM") == "dumb":
        return True
    return False


class Output:
    def __init__(self) -> None:
        no_color = _detect_no_color()
        self._console = Console(
            no_color=no_color,
            highlight=not no_color,
        )
        self._err_console = Console(
            stderr=True,
            no_color=no_color,
            highlight=not no_color,
        )
        self._mode = OutputMode.PLAIN if no_color else OutputMode.RICH
        self._verbose = False
        self._quiet = False
        self._no_input = False
        self._json_data: dict[str, Any] | None = None

    @property
    def mode(self) -> OutputMode:
        return self._mode

    @property
    def is_json(self) -> bool:
        return self._mode == OutputMode.JSON

    @property
    def no_input(self) -> bool:
        return self._no_input

    @property
    def console(self) -> Console:
        return self._console

    def configure(
        self,
        *,
        json_mode: bool = False,
        verbose: bool = False,
        quiet: bool = False,
        no_input: bool = False,
        no_color: bool = False,
    ) -> None:
        self._verbose = verbose
        self._quiet = quiet
        self._no_input = no_input or not sys.stdin.isatty()

        force_no_color = no_color or _detect_no_color()
        if force_no_color:
            self._console = Console(no_color=True, highlight=False)
            self._err_console = Console(
                stderr=True, no_color=True, highlight=False,
            )

        if json_mode:
            self._mode = OutputMode.JSON
            self._json_data = {}
        elif force_no_color:
            self._mode = OutputMode.PLAIN

    def print(self, *args: Any, **kwargs: Any) -> None:
        if self._mode == OutputMode.JSON:
            return
        if self._quiet:
            return
        self._console.print(*args, **kwargs)

    def error(self, message: str) -> None:
        if self._mode == OutputMode.JSON:
            self._err_console.print(message)
            return
        self._err_console.print(f"[red]{message}[/red]")

    def success(self, message: str) -> None:
        if self._mode == OutputMode.JSON:
            return
        if self._quiet:
            return
        self._console.print(f"[green]{message}[/green]")

    def debug(self, message: str) -> None:
        if not self._verbose:
            return
        if self._mode == OutputMode.JSON:
            return
        self._err_console.print(f"[dim]{message}[/dim]")

    def table(self, table: Table) -> None:
        if self._mode == OutputMode.JSON:
            return
        if self._quiet:
            return
        self._console.print(table)

    def json_result(self, data: dict[str, Any] | list[Any]) -> None:
        if self._mode == OutputMode.JSON:
            self._console.print_json(json.dumps(data))
        else:
            self._console.print_json(json.dumps(data))

    def emit(
        self,
        *,
        data: dict[str, Any] | list[Any],
        rich_fn: Any | None = None,
    ) -> None:
        if self._mode == OutputMode.JSON:
            self._console.print_json(json.dumps(data))
        elif rich_fn is not None:
            rich_fn()

    def safe_prompt(
        self,
        message: str,
        default: str | None = None,
        hide_input: bool = False,
    ) -> str:
        import typer

        if self._no_input:
            if default is not None:
                return default
            self.error(
                f"Cannot prompt for '{message}' in non-interactive mode. "
                "Use flags or env vars instead."
            )
            raise typer.Exit(1)
        return typer.prompt(message, default=default, hide_input=hide_input)

    def safe_confirm(
        self,
        message: str,
        default: bool = False,
    ) -> bool:
        import typer

        if self._no_input:
            return default
        return typer.confirm(message, default=default)


_output: Output | None = None


def get_output() -> Output:
    global _output
    if _output is None:
        _output = Output()
    return _output


def reset_output() -> None:
    global _output
    _output = None


EXIT_OK = 0
EXIT_USER_ERROR = 1
EXIT_INTERNAL_ERROR = 2
