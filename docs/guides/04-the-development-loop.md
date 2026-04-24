# The Development Loop

The pad has a sidebar, editor, preview, toolbar, and event log in place, but the preview pane is empty. In this chapter we bring it to life with two complementary techniques: hot reload for editing the pad's own source, and runtime compilation for turning the editor buffer into a rendered widget tree.

Along the way we pick up a few debugging habits: inspecting the initial UI tree with `python -m plushie inspect`, watching renderer stderr, and using `print()` and `runtime.inject()` to probe the update cycle.

## Hot reload

The `run` subcommand accepts a `--watch` flag that enables filesystem-based hot reload:

```bash
python -m plushie run plushie_pad:Pad --watch
```

Under the hood this spawns a `DevServer` (`plushie.dev_server`) which:

- watches the `src/`, `lib/`, and current directories for `.py` changes,
- uses the `watchfiles` library when available (Rust-backed, fast), falling back to mtime polling,
- debounces bursts of filesystem events with a hardcoded 300 ms window,
- reimports the app module with `importlib.reload`, reinstantiates the `App` subclass, and sends a fresh snapshot to the renderer.

Edit `plushie_pad/app.py`, save, and the pad rerenders with your changes. The current model survives the reload because the runtime holds it directly: only the `App` instance (which holds no state) is replaced.

Pair `--watch` with `--daemon` to keep the runtime alive across renderer restarts:

```bash
python -m plushie run plushie_pad:Pad --watch --daemon
```

In daemon mode the runtime stays up if the renderer process dies or is closed. Model state, async tasks, and subscriptions persist. Hot reload then feels seamless: edit, save, the renderer repaints, state is intact.

Hot reload has limits. It works because `view()` is a pure function of the model, so re-running it after recompilation produces a new tree the runtime can diff. Changes to `init()` do not apply retroactively (the model has already been built). Changes to `update()` apply to the next event, not past ones. If you need a clean slate, restart the process.

See the [CLI commands reference](../reference/cli-commands.md) for the full flag list.

## Runtime experiment compilation

Hot reload handles the pad's own code. The preview pane needs something different: it must compile and run whatever Python source the user has typed into the editor, without restarting the pad.

Python gives us the two builtins we need. `compile()` parses source into a code object. `exec()` runs that code object against a namespace dict. Together they let us treat the editor buffer as a tiny module.

Add `plushie_pad/compile.py`:

```python
"""Runtime compilation of experiment source."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

_cache: dict[str, Any] = {}


@dataclass(frozen=True, slots=True)
class CompileError:
    """A compilation or execution error from an experiment."""

    message: str
    phase: str  # "compile" or "exec"


def compile_experiment(
    name: str, source: str
) -> tuple[dict[str, Any] | None, CompileError | None]:
    """Compile and execute ``source`` as an experiment module.

    Returns ``(namespace, None)`` on success, ``(None, error)`` on
    failure. ``namespace`` is the module-level dict containing the
    experiment's top-level bindings (notably ``view``).
    """
    key = hashlib.sha256(source.encode()).hexdigest()
    if key in _cache:
        return _cache[key], None

    try:
        code = compile(source, f"<experiment:{name}>", "exec")
    except SyntaxError as exc:
        return None, CompileError(message=str(exc), phase="compile")

    namespace: dict[str, Any] = {"__name__": f"experiment_{name}"}
    try:
        exec(code, namespace)
    except Exception as exc:  # noqa: BLE001
        return None, CompileError(message=f"{type(exc).__name__}: {exc}", phase="exec")

    _cache[key] = namespace
    return namespace, None


def call_view(namespace: dict[str, Any]) -> tuple[Any, CompileError | None]:
    """Invoke ``namespace["view"]()`` and return the rendered node."""
    view = namespace.get("view")
    if not callable(view):
        return None, CompileError(
            message="experiment must define a top-level view() callable",
            phase="exec",
        )
    try:
        return view(), None
    except Exception as exc:  # noqa: BLE001
        return None, CompileError(message=f"{type(exc).__name__}: {exc}", phase="exec")


def clear_cache() -> None:
    """Reset the compile cache. Used in tests."""
    _cache.clear()
```

Three things to notice.

The cache is keyed by a SHA-256 of the source. Identical source hits the cache; a single keystroke produces a new hash and a fresh compile. The pad calls `compile_experiment()` from `view()`, which runs on every render, so without the cache we would recompile constantly. With it, idle renders are free.

`compile()` raises `SyntaxError` with a readable message. `exec()` can raise anything (a `NameError` from a missing import, a `TypeError` from bad kwargs, anything the user's code does). Both paths feed a `CompileError` with a `phase` tag so callers can distinguish syntax from runtime failures.

The namespace is a plain dict. It is not registered in `sys.modules`, so experiments cannot import each other by name. That is fine for the pad: each experiment is a single file.

## Wiring up the preview pane

The pad's model already has `editor_source` and `preview_error` fields. The preview pane's `view()` helper compiles the editor buffer on every render, calls `view()` on the resulting namespace, and wraps the returned node in a container:

```python
def _preview(model: Model) -> dict[str, Any]:
    if model.preview_error is not None:
        return ui.container(
            "preview",
            ui.text("error", model.preview_error.message, color="#d32f2f"),
            padding=12,
            width="fill",
            height={"fill_portion": 2},
        )
    namespace, err = pad_compile.compile_experiment(
        model.selected or "unnamed", model.editor_source
    )
    if err is not None or namespace is None:
        return ui.container(
            "preview",
            ui.text("error", err.message if err else "compile failed", color="#d32f2f"),
            padding=12,
            width="fill",
            height={"fill_portion": 2},
        )
    node, call_err = pad_compile.call_view(namespace)
    if call_err is not None or node is None:
        return ui.container(
            "preview",
            ui.text(
                "error",
                call_err.message if call_err else "view() failed",
                color="#d32f2f",
            ),
            padding=12,
            width="fill",
            height={"fill_portion": 2},
        )
    return ui.container(
        "preview",
        node,
        padding=12,
        width="fill",
        height={"fill_portion": 2},
    )
```

Run the pad:

```bash
python -m plushie run plushie_pad:Pad --watch
```

The starter experiment (saved the first time the pad boots) compiles on init, so the preview shows "Hello, Plushie!" and a button straight away. Edit the editor buffer and the preview updates on each keystroke, throttled by the compile cache.

## Handling compile errors

The `CompileError` dataclass carries a `message` and a `phase` (`"compile"` or `"exec"`). The pad shows the message as red text inside the preview container. The pad itself never crashes, even when the experiment does something catastrophic: the `exec()` exception is caught, wrapped, and displayed.

Try it yourself. In the editor, delete a closing parenthesis and watch the `SyntaxError` appear. Then reference an undefined name (`ui.buttton("x", "x")`) and watch the `AttributeError` appear with the `exec` phase.

For experiments that raise in `view()` itself, `call_view()` catches the error and returns it the same way. The caller cannot tell whether the failure was at import time or at render time unless it looks at `phase`.

## REPL inspection

Before running the pad in a window, it is sometimes useful to see what tree the app produces on init. The `inspect` subcommand does exactly that: it imports the App class, calls `init()`, calls `view()` on the returned model, normalizes the tree, and prints it as JSON.

```bash
python -m plushie inspect plushie_pad:Pad
```

Trimmed output:

```json
{
  "id": "pad",
  "type": "window",
  "props": { "title": "Plushie Pad", "size": [1100, 700] },
  "children": [
    {
      "id": "auto:row:pad:0",
      "type": "row",
      "children": [
        { "id": "sidebar", "type": "container", "children": [ ... ] },
        { "id": "auto:column:...", "type": "column", "children": [ ... ] },
        { "id": "log", "type": "container", "children": [ ... ] }
      ]
    }
  ]
}
```

This is the same normalized tree the runtime sends on the first snapshot. Auto-generated IDs (`auto:row:pad:0`) appear for nodes you did not name explicitly. If you are debugging a layout glitch and suspect a tree-shape issue, `inspect` lets you see the structure without launching a window.

See the [app lifecycle reference](../reference/app-lifecycle.md) for how `init`, `view`, and `normalize` compose.

## Debugging tips

A few habits that pay off:

**Watch renderer stderr.** The renderer prints diagnostics to stderr. When you run in a terminal, those lines interleave with your app's stdout. If a widget silently fails to render, check stderr first: the renderer almost always says something.

**Trace `update` with `print`.** Adding a `print(event)` at the top of `update` shows you exactly what the runtime dispatches. This is the fastest way to answer "did the click I pressed actually arrive?" Events are dataclasses with `__repr__`, so the output is readable without formatting.

**Inject events from elsewhere.** The `Runtime.inject(event)` method is thread-safe. A Flask route, a background thread, or an `iex`-style REPL script can hand the runtime a synthetic event that flows through `update` like any other. Useful for reproducing bugs that depend on timing or for scripting demos.

**Use `--mode headless` to rule out windowing issues.** If a test or experiment behaves oddly with real windows, rerun with `--mode headless` to take display compositing out of the picture.

See the [testing guide](../reference/testing.md) for the full driver API and how to script interactions through `AppFixture`.

## Preflight

Before committing, run the preflight script from the repo root:

```bash
./preflight
```

This mirrors CI: `ruff format --check`, `ruff check`, `pyright src`, and `pytest`. If `preflight` does not exist yet in your checkout, run the individual commands in the same order. See the [configuration reference](../reference/configuration.md) for the environment variables (`PLUSHIE_BINARY_PATH`, `PLUSHIE_TEST_BACKEND`) that control how the tests find and drive the renderer.

Fast feedback matters more than perfect hygiene between commits: run `pytest -k <name>` while iterating and save the full preflight for the end.

## What's next

With hot reload, runtime compilation, and a working preview pane, the pad is finally something you can tinker in. In [chapter 5](05-events.md) we wire the event log pane up to the runtime's event stream so you can see exactly what widgets produce as you interact with them.

---

Next: [Events](05-events.md)
