"""Tests mirroring the getting-started guide code examples.

<!-- test: test_getting_started_counter_init, test_getting_started_counter_increment,
     test_getting_started_counter_decrement, test_getting_started_counter_unknown_event,
     test_getting_started_counter_view, test_getting_started_counter_view_after_increments
     -- keep the getting-started counter code block in sync with these tests -->

<!-- test: test_getting_started_decorator_init, test_getting_started_decorator_increment,
     test_getting_started_decorator_unknown_event, test_getting_started_decorator_view
     -- keep the getting-started decorator code block in sync with these tests -->
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.events import Click

# -- Class-based counter reproduced from getting-started doc --


@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0


class Counter(plushie.App[Model]):
    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            case Click(id="inc"):
                return replace(model, count=model.count + 1)
            case Click(id="dec"):
                return replace(model, count=model.count - 1)
            case _:
                return model

    def view(self, model: Model) -> dict[str, Any]:
        return ui.window(
            "main",
            ui.column(
                ui.text("count", f"Count: {model.count}", size=20),
                ui.row(
                    ui.button("inc", "+"),
                    ui.button("dec", "-"),
                    spacing=8,
                ),
                padding=16,
                spacing=8,
            ),
            title="Counter",
        )


# -- Decorator-based counter reproduced from getting-started doc --

decorator_app = plushie.create_app()


@decorator_app.init
def dec_init() -> dict[str, int]:
    return {"count": 0}


@decorator_app.update
def dec_update(model: dict[str, int], event: object) -> dict[str, int]:
    match event:
        case Click(id="inc"):
            return {**model, "count": model["count"] + 1}
        case _:
            return model


@decorator_app.view
def dec_view(model: dict[str, int]) -> dict[str, Any]:
    return ui.window(
        "main",
        ui.column(
            ui.text("count", f"Count: {model['count']}"),
            ui.button("inc", "+"),
            padding=16,
            spacing=8,
        ),
        title="Counter",
    )


# -- Class-based counter tests --


def test_getting_started_counter_init() -> None:
    app = Counter()
    model = app.init()
    assert model.count == 0


def test_getting_started_counter_increment() -> None:
    app = Counter()
    model = app.init()
    model = app.update(model, Click(id="inc"))
    assert model.count == 1


def test_getting_started_counter_decrement() -> None:
    app = Counter()
    model = app.init()
    model = app.update(model, Click(id="dec"))
    assert model.count == -1


def test_getting_started_counter_unknown_event() -> None:
    app = Counter()
    model = app.init()
    model = app.update(model, Click(id="unknown"))
    assert model.count == 0


def test_getting_started_counter_view() -> None:
    app = Counter()
    model = app.init()
    tree = app.view(model)

    assert tree["type"] == "window"
    assert tree["id"] == "main"
    assert tree["props"]["title"] == "Counter"

    children = tree["children"]
    assert len(children) == 1
    column = children[0]
    assert column["type"] == "column"
    assert column["props"]["padding"] == 16
    assert column["props"]["spacing"] == 8

    col_children = column["children"]
    assert len(col_children) == 2
    text_node = col_children[0]
    row_node = col_children[1]

    assert text_node["type"] == "text"
    assert text_node["props"]["content"] == "Count: 0"
    assert text_node["props"]["size"] == 20

    assert row_node["type"] == "row"
    row_children = row_node["children"]
    assert len(row_children) == 2
    assert row_children[0]["id"] == "inc"
    assert row_children[0]["props"]["label"] == "+"
    assert row_children[1]["id"] == "dec"
    assert row_children[1]["props"]["label"] == "-"


def test_getting_started_counter_view_after_increments() -> None:
    app = Counter()
    model = app.init()
    model = app.update(model, Click(id="inc"))
    model = app.update(model, Click(id="inc"))
    tree = app.view(model)

    column = tree["children"][0]
    text_node = column["children"][0]
    assert text_node["props"]["content"] == "Count: 2"


# -- Decorator-based counter tests --


def test_getting_started_decorator_init() -> None:
    built = decorator_app.build()
    model = built.init()
    assert model == {"count": 0}


def test_getting_started_decorator_increment() -> None:
    built = decorator_app.build()
    model = built.init()
    result = built.update(model, Click(id="inc"))
    assert isinstance(result, dict)
    assert result["count"] == 1


def test_getting_started_decorator_unknown_event() -> None:
    built = decorator_app.build()
    model = built.init()
    result = built.update(model, Click(id="unknown"))
    assert isinstance(result, dict)
    assert result["count"] == 0


def test_getting_started_decorator_view() -> None:
    built = decorator_app.build()
    model = built.init()
    tree = built.view(model)

    assert isinstance(tree, dict)
    assert tree["type"] == "window"
    assert tree["id"] == "main"
    assert tree["props"]["title"] == "Counter"

    column = tree["children"][0]
    assert column["type"] == "column"
    assert column["props"]["padding"] == 16

    col_children = column["children"]
    assert len(col_children) == 2
    text_node = col_children[0]
    assert text_node["type"] == "text"
    assert text_node["props"]["content"] == "Count: 0"

    btn = col_children[1]
    assert btn["id"] == "inc"
    assert btn["props"]["label"] == "+"
