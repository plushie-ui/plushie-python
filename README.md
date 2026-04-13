# plushie

Build native desktop apps in Python. **[Pre-1.0](#status)**

Write your entire application in Python (state, events, UI) and get
native windows on Linux, macOS, and Windows. Available on
[PyPI](https://pypi.org/project/plushie/) as `plushie`. The
[renderer](https://github.com/plushie-ui/plushie-rust) is built on
[Iced](https://github.com/iced-rs/iced) and ships as a precompiled
binary, no Rust toolchain required.

SDKs are also available for
[Elixir](https://github.com/plushie-ui/plushie-elixir),
[Gleam](https://github.com/plushie-ui/plushie-gleam),
[Ruby](https://github.com/plushie-ui/plushie-ruby), and
[TypeScript](https://github.com/plushie-ui/plushie-typescript).

## Quick start

<!-- test: test_readme_counter_init, test_readme_counter_increment, test_readme_counter_decrement, test_readme_counter_unknown_event, test_readme_counter_view_structure, test_readme_counter_view_after_increment -- keep this code block in sync with tests/docs/test_readme.py -->

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click


@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0


class Counter(plushie.App[Model]):
    def init(self):
        return Model()

    def update(self, model, event):
        match event:
            case Click(id="inc"):
                return replace(model, count=model.count + 1)
            case Click(id="dec"):
                return replace(model, count=model.count - 1)
            case _:
                return model

    def view(self, model):
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


if __name__ == "__main__":
    plushie.run(Counter)
```

Install and run:

```bash
pip install plushie
python -m plushie download              # download precompiled binary
python -m plushie run counter:Counter   # run the counter example
```

The repo includes [several examples](examples/) you can try, from a
minimal counter to a full widget catalog. Edit them while the GUI is
running and see changes instantly. For complete project demos,
including native Rust extensions, see the
[plushie-demos](https://github.com/plushie-ui/plushie-demos/tree/main/python)
repo.

To add Plushie to your own project, see the
[getting started guide](docs/getting-started.md), or browse the
[docs](docs/) for all guides and references.

## How it works

Under the hood, a renderer built on
[iced](https://github.com/iced-rs/iced) handles window drawing and
platform integration. Your Python code sends widget trees to the
renderer over stdin; the renderer draws native windows and sends
user events back over stdout.

You don't need Rust to use plushie. The renderer is a precompiled
binary, similar to how your app talks to a database without you
writing C. If you ever need custom native rendering, the
[extension system](docs/extensions.md) lets you write Rust for just
those parts.

The same protocol works over a local pipe, an SSH connection, or
any bidirectional byte stream - your code doesn't need to change.
See the [running guide](docs/running.md) for deployment options.

## Features

- **Elm architecture** - init, update, view. State lives in
  Python, pure functions, predictable updates
- **Built-in widgets** - layout, input, display, and interactive
  widgets out of the box
- **Canvas** - shapes, paths, gradients, transforms, and
  interactive elements for custom 2D drawing
- **Themes** - dark, light, nord, catppuccin, tokyo night, and
  more, with custom palettes and per-widget style overrides
- **Animation** - renderer-side transitions, springs, and
  sequences with no wire traffic per frame
- **Multi-window** - declare windows in your view; the framework
  manages the rest
- **Platform effects** - native file dialogs, clipboard, OS
  notifications
- **Accessibility** - keyboard navigation, screen readers, and
  focus management via [AccessKit](https://accesskit.dev)
- **Custom widgets** - compose existing widgets in pure Python,
  draw on the canvas, or extend with native Rust
- **Hot reload** - edit code, see changes instantly with full
  state preservation
- **Remote rendering** - app on a server or embedded device,
  renderer on a display machine over SSH or any byte stream
- **Fault-tolerant** - renderer crashes auto-recover; app
  exceptions are caught and state reverted

## Testing and automation

Tests run through the real renderer binary, not mocks. Interact like
a user: click, type, find elements, assert on text. Three
interchangeable backends:

- **Mock** - millisecond tests, no display server
- **Headless** - real rendering via
  [tiny-skia](https://github.com/linebender/tiny-skia), supports
  screenshots for pixel regression in CI
- **Windowed** - real windows with GPU rendering, platform effects,
  real input

```python
import pytest
from plushie.testing import AppFixture
from todo import TodoApp, Model


@pytest.fixture
def app(plushie_pool):
    with AppFixture(TodoApp, plushie_pool) as f:
        yield f


def test_add_and_complete_todo(app):
    app.type_text("#new-todo", "Buy milk")
    app.submit("#new-todo")

    app.assert_exists("#todo-1")
    assert app.model.items[0].text == "Buy milk"

    app.toggle("#todo-1/done")
    assert app.model.items[0].done is True

    app.select("#filter", "done")
    app.assert_not_exists("#todo-1")
```

```bash
pytest                                    # mock (fast, no display)
PLUSHIE_TEST_BACKEND=headless pytest      # real rendering, no display
PLUSHIE_TEST_BACKEND=windowed pytest      # real windows (needs display)
```

See the [testing guide](docs/testing.md) for the full API, backend
details, and CI configuration.

## Status

Pre-1.0. The core works (built-in widgets, event system, themes,
multi-window, testing framework, accessibility) but the API is
still evolving. Pin to an exact version and read the
[CHANGELOG](CHANGELOG.md) when upgrading.

## License

MIT
