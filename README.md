# plushie

Build native desktop apps in Python. **Pre-1.0**

Plushie is a desktop GUI framework that lets you write your entire
application in Python -- state, events, UI -- and get native windows
on Linux, macOS, and Windows. Rendering is powered by
[iced](https://github.com/iced-rs/iced), a cross-platform GUI library
for Rust, which plushie drives as a precompiled binary behind the scenes.

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

```bash
python -m plushie run counter:Counter
```

## Getting started

```bash
pip install plushie
python -m plushie download    # download precompiled renderer
python -m plushie run counter:Counter
```

The precompiled binary requires no Rust toolchain. To build from
source instead, install [rustup](https://rustup.rs/) and run
`python -m plushie build`.

## Features

- **38 built-in widget types** -- buttons, text inputs, sliders,
  tables, markdown, canvas, and more.
- **22 built-in themes** -- light, dark, dracula, nord, solarized,
  gruvbox, catppuccin, tokyo night, kanagawa, and more.
- **Multi-window** -- declare window nodes in your view; the
  framework manages them automatically.
- **Platform effects** -- native file dialogs, clipboard, OS
  notifications.
- **Accessibility** -- screen reader support via accesskit.
- **Remote rendering** -- native desktop UI for apps running on
  servers or embedded devices, over SSH.

## Testing

Plushie ships a test framework with three interchangeable backends.
Write your tests once, run them at whatever fidelity you need:

```python
import pytest
from plushie.testing import AppFixture
from counter import Counter, Model


@pytest.fixture
def app(plushie_pool):
    with AppFixture(Counter, pool=plushie_pool) as f:
        yield f


def test_increment(app):
    app.click("#inc")
    assert app.model.count == 1
```

```bash
pytest                                    # mock (fast, no display)
PLUSHIE_TEST_BACKEND=headless pytest      # real rendering, no display
PLUSHIE_TEST_BACKEND=windowed pytest      # real windows
```

## How it works

A renderer built on [iced](https://github.com/iced-rs/iced) handles
window drawing and platform integration. Your Python code sends widget
trees to the renderer over stdin; the renderer draws native windows and
sends user events back over stdout.

You don't need Rust to use plushie. The renderer is a precompiled
binary, similar to how your app talks to a database without you
writing C.

## Documentation

- [Wire protocol](https://github.com/plushie-ui/plushie/blob/main/docs/protocol.md)

## Status

Pre-1.0. The core is being built. Pin to an exact version.

## License

MIT
