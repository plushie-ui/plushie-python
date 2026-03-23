"""Tests mirroring the README counter example.

<!-- test: test_readme_counter_init, test_readme_counter_increment,
     test_readme_counter_decrement, test_readme_counter_unknown_event,
     test_readme_counter_view_structure, test_readme_counter_view_after_increment
     -- keep the README code block in sync with these tests -->
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from plushie import ui
from plushie.events import Click

# -- Types reproduced from the README counter example --


@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0


def init() -> Model:
    return Model()


def update(model: Model, event: object) -> Model:
    match event:
        case Click(id="inc"):
            return replace(model, count=model.count + 1)
        case Click(id="dec"):
            return replace(model, count=model.count - 1)
        case _:
            return model


def view(model: Model) -> dict:
    return ui.window(
        "main",
        ui.column(
            ui.text("count", f"Count: {model.count}"),
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


# -- Tests --


def test_readme_counter_init() -> None:
    model = init()
    assert model.count == 0


def test_readme_counter_increment() -> None:
    model = init()
    model = update(model, Click(id="inc"))
    assert model.count == 1


def test_readme_counter_decrement() -> None:
    model = init()
    model = update(model, Click(id="dec"))
    assert model.count == -1


def test_readme_counter_unknown_event() -> None:
    model = init()
    model = update(model, Click(id="nope"))
    assert model.count == 0


def test_readme_counter_view_structure() -> None:
    tree = view(Model(count=0))

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

    assert row_node["type"] == "row"
    assert row_node["props"]["spacing"] == 8
    row_children = row_node["children"]
    assert len(row_children) == 2
    assert row_children[0]["id"] == "inc"
    assert row_children[0]["props"]["label"] == "+"
    assert row_children[1]["id"] == "dec"
    assert row_children[1]["props"]["label"] == "-"


def test_readme_counter_view_after_increment() -> None:
    tree = view(Model(count=3))
    column = tree["children"][0]
    text_node = column["children"][0]
    assert text_node["props"]["content"] == "Count: 3"
