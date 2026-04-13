"""Async fetch: demonstrates Command.task for background work.

Features exercised:

- ``Command.task`` with a function that simulates fetching data
- ``AsyncResult`` handling for success and failure
- Loading state in the model
- Error handling (the task function may raise)

Run::

    python -m plushie run examples.async_fetch:FetchApp
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.commands import Command
from plushie.events import AsyncResult, Click


@dataclass(frozen=True, slots=True)
class Model:
    """Fetch app model: tracks loading state and fetched data."""

    loading: bool = False
    data: str | None = None
    error: str | None = None


def _simulate_fetch() -> str:
    """Simulate a slow network request.

    In a real app this would be ``urllib.request.urlopen(url).read()``
    or similar.  We sleep briefly to demonstrate the loading state.
    """
    time.sleep(0.5)
    return "Hello from the background thread!"


def _simulate_fetch_error() -> str:
    """Simulate a failed network request."""
    time.sleep(0.5)
    msg = "Connection timed out"
    raise TimeoutError(msg)


class FetchApp(plushie.App[Model]):
    """Demonstrates async work via Command.task."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model | tuple[Model, Command]:
        match event:
            case Click(id="fetch"):
                return (
                    replace(model, loading=True, data=None, error=None),
                    Command.task(_simulate_fetch, "fetch"),
                )

            case Click(id="fetch-error"):
                return (
                    replace(model, loading=True, data=None, error=None),
                    Command.task(_simulate_fetch_error, "fetch"),
                )

            case AsyncResult(tag="fetch", value=v) if isinstance(v, Exception):
                return replace(model, loading=False, error=str(v))

            case AsyncResult(tag="fetch", value=v):
                return replace(model, loading=False, data=str(v))

            case _:
                return model

    def view(self, model: Model) -> dict:
        status: str
        if model.loading:
            status = "Loading..."
        elif model.error is not None:
            status = f"Error: {model.error}"
        elif model.data is not None:
            status = model.data
        else:
            status = "Press a button to fetch data."

        return ui.window(
            "main",
            ui.column(
                ui.text("status", status),
                ui.row(
                    ui.button("fetch", "Fetch Data"),
                    ui.button("fetch-error", "Fetch (Error)"),
                    spacing=8,
                ),
                padding=16,
                spacing=8,
            ),
            title="Async Fetch",
        )


if __name__ == "__main__":
    plushie.run(FetchApp)
