# plushie

Build native desktop apps in Python. **[Pre-1.0](#status)**

Plushie is a desktop GUI framework that allows you to write your entire
application in Python -- state, events, UI -- and get native windows
on Linux, macOS, and Windows. Rendering is powered by
[iced](https://github.com/iced-rs/iced), a cross-platform GUI library
for Rust, which plushie drives as a precompiled binary behind the scenes.

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

```bash
python -m plushie run counter:Counter
```

This is one of [9 examples](examples/) included in the repo, from a
minimal counter to a full widget catalog. Edit them while the GUI is
running and see changes instantly. For complete project demos,
including native Rust extensions, see the
[plushie-demos](https://github.com/plushie-ui/plushie-demos/tree/main/python)
repository.

## Getting started

Install plushie:

```bash
pip install plushie
```

Then:

```bash
python -m plushie download              # download precompiled binary
python -m plushie run counter:Counter   # run the counter example
```

Pin to an exact version and read the
[CHANGELOG](CHANGELOG.md) carefully when upgrading.

The precompiled binary requires no Rust toolchain. To build from
source instead, install [rustup](https://rustup.rs/) and run
`python -m plushie build`. See the
[getting started guide](docs/getting-started.md) for the full
walkthrough.

## Features

- **38 built-in widget types** -- buttons, text inputs, sliders,
  tables, markdown, canvas, and more. Easy to build your own.
  [Layout guide](docs/layout.md)
- **22 built-in themes** -- light, dark, dracula, nord, solarized,
  gruvbox, catppuccin, tokyo night, kanagawa, and more. Custom
  palettes and per-widget style overrides.
  [Theming guide](docs/theming.md)
- **Multi-window** -- declare window nodes in your widget tree;
  the framework opens, closes, and manages them automatically.
  [App guide](docs/app.md)
- **Platform effects** -- native file dialogs, clipboard, OS
  notifications. [Effects guide](docs/effects.md)
- **Accessibility** -- screen reader support via
  [accesskit](https://accesskit.dev) on all platforms.
  [Accessibility guide](docs/accessibility.md)
- **Live reload** -- edit code, see changes instantly. Use
  `python -m plushie run myapp:App --watch`.
- **Extensions** -- multiple paths to custom widgets:
  - **Compose** existing widgets into higher-level components with
    pure Python. No Rust, no binary rebuild.
  - **Draw** on the canvas with shape primitives for charts, gauges,
    diagrams, and other custom 2D rendering.
  - **Native** -- implement `WidgetExtension` in Rust for full
    control over rendering, state, and event handling.
  - [Extensions guide](docs/extensions.md)
- **Remote rendering** -- native desktop UI for apps running on
  servers or embedded devices. Dashboards, admin tools, IoT
  diagnostics -- over SSH with configurable event throttling.
  [Running guide](docs/running.md)

## Testing

Plushie ships a test framework with three interchangeable backends.
Write your tests once, run them at whatever fidelity you need:

- **Mock** -- millisecond tests, no display server. Uses a shared
  mock process for fast logic and interaction testing.
- **Headless** -- real rendering via
  [tiny-skia](https://github.com/linebender/tiny-skia), no display
  server needed. Supports screenshots for pixel regression in CI.
- **Windowed** -- real windows with GPU rendering. Platform effects,
  real input, the works.

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
any bidirectional byte stream -- your code doesn't need to change.
See the [running guide](docs/running.md) for deployment options.

## Status

Pre-1.0. The core works -- 38 widget types, event system, 22 themes,
multi-window, testing framework, accessibility -- but the API is
still evolving:

- Pin to an exact version and read the
  [CHANGELOG](CHANGELOG.md) when upgrading.
- The extension system is the least stable part of the API.

## Documentation

Guides are in [`docs/`](docs/):

- [Getting started](docs/getting-started.md) -- setup, first app, CLI commands, dev mode
- [Tutorial](docs/tutorial.md) -- build a todo app step by step
- [App](docs/app.md) -- the Python API contract, multi-window
- [Layout](docs/layout.md) -- length, padding, alignment, spacing
- [Events](docs/events.md) -- full event taxonomy
- [Commands and subscriptions](docs/commands.md) -- async work, timers, widget ops
- [Effects](docs/effects.md) -- native platform features
- [Theming](docs/theming.md) -- themes, custom palettes, styling
- [Composition patterns](docs/composition-patterns.md) -- tabs, sidebars, modals, cards, state helpers
- [Scoped IDs](docs/scoped-ids.md) -- hierarchical ID namespacing
- [Testing](docs/testing.md) -- three-backend test framework and pixel regression
- [Accessibility](docs/accessibility.md) -- accesskit integration, a11y props
- [Extensions](docs/extensions.md) -- custom widgets, Rust extensions, publishing packages
- [Running](docs/running.md) -- remote rendering, transports, deployment
- [CLI reference](docs/cli.md) -- all commands and flags
- [Standalone executables](docs/standalone.md) -- PyInstaller, Nuitka, Briefcase

## Development

```bash
./preflight                              # run all CI checks locally
```

Mirrors CI and stops on first failure: format, lint, type check, test.

## System requirements

The precompiled binary (`python -m plushie download`) has no additional
dependencies beyond Python 3.12+. To build from source, install a
Rust toolchain via [rustup](https://rustup.rs/) and the
platform-specific libraries:

- **Linux (Debian/Ubuntu):**
  `sudo apt-get install libxkbcommon-dev libwayland-dev libx11-dev cmake fontconfig pkg-config`
- **Linux (Arch):**
  `sudo pacman -S libxkbcommon wayland libx11 cmake fontconfig pkgconf`
- **macOS:** `xcode-select --install`
- **Windows:**
  [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
  with "Desktop development with C++"

## Links

| | |
|---|---|
| Python SDK | [github.com/plushie-ui/plushie-python](https://github.com/plushie-ui/plushie-python) |
| Elixir SDK | [github.com/plushie-ui/plushie-elixir](https://github.com/plushie-ui/plushie-elixir) |
| Renderer | [github.com/plushie-ui/plushie](https://github.com/plushie-ui/plushie) |
| Demo projects | [github.com/plushie-ui/plushie-demos](https://github.com/plushie-ui/plushie-demos) |

## License

MIT
