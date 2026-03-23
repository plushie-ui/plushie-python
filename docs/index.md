# plushie

Build native desktop apps in Python.

Plushie is a desktop GUI framework that lets you write your entire
application in Python -- state, events, UI -- and get native windows
on Linux, macOS, and Windows. Rendering is powered by
[iced](https://github.com/iced-rs/iced), a cross-platform GUI library
for Rust, which plushie drives as a precompiled binary behind the scenes.

## Quick start

Install plushie and download the renderer:

```bash
pip install plushie
python -m plushie download
```

Create a counter app:

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

Run it:

```bash
python -m plushie run counter:Counter
```

## Guides

- [Getting started](getting-started.md) -- setup, first app, CLI commands, dev mode
- [Tutorial](tutorial.md) -- build a todo app step by step
- [App](app.md) -- the Python API contract, multi-window
- [Layout](layout.md) -- length, padding, alignment, spacing
- [Events](events.md) -- full event taxonomy
- [Commands](commands.md) -- async work, timers, widget ops
- [Effects](effects.md) -- native platform features
- [Theming](theming.md) -- themes, custom palettes, styling
- [Composition patterns](composition-patterns.md) -- tabs, sidebars, modals, cards
- [Scoped IDs](scoped-ids.md) -- hierarchical ID namespacing
- [Testing](testing.md) -- three-backend test framework and pixel regression
- [Accessibility](accessibility.md) -- accesskit integration, a11y props
- [Extensions](extensions.md) -- custom widgets, Rust extensions
- [Running](running.md) -- remote rendering, transports, deployment

## Reference

- [CLI reference](cli.md) -- all commands and flags
- [Standalone executables](standalone.md) -- PyInstaller, Nuitka, Briefcase

## Links

- [GitHub](https://github.com/plushie-ui/plushie-python)
- [Changelog](https://github.com/plushie-ui/plushie-python/blob/main/CHANGELOG.md)
- [Elixir SDK](https://github.com/plushie-ui/plushie-elixir)
- [Renderer (Rust)](https://github.com/plushie-ui/plushie-renderer)
