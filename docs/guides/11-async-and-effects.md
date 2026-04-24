# Async and Effects

The pad saves experiments to disk inside `update`, which works only because the filesystem call is fast and always local. Real apps reach for slower operations: opening a file picker, copying to the clipboard, hitting an API, running a linter. Doing any of that synchronously inside `update` would freeze the event loop and stall the UI.

This chapter introduces the two primitives Plushie gives you for that kind of work: commands for background Python functions, and effects for platform operations handled by the renderer. Along the way the pad picks up import, export, clipboard copy, and a streaming linter with live progress.

## Returning commands from update

So far every `update` branch has returned either a bare model or the model unchanged. Commands are the second half of the return tuple:

```python
from dataclasses import replace

import plushie
from plushie import Command, ui
from plushie.events import AsyncResult, Click, EffectResult, StreamChunk
from plushie.events import EffectCancelled, FileOpened, FileSaved


def update(self, model, event):
    match event:
        case Click(id="save"):
            return replace(model, saving=True), Command.task(_write_file, "save")
        case AsyncResult(tag="save", value=path):
            return replace(model, saving=False, last_saved=path)
        case _:
            return model
```

The runtime accepts any of these return shapes from `update`:

```python
return model                           # no side effect
return model, Command.none()           # same thing, explicit
return model, Command.task(fn, "tag")  # one command
return model, [cmd_a, cmd_b]           # a list becomes a batch
```

A list is shorthand for `Command.batch(...)`. Commands in a batch run in the order given. `update` itself never blocks on the command; it hands the descriptor back to the runtime, which dispatches it on the appropriate thread.

## Command.task: background Python work

`Command.task(fn, tag)` submits `fn` to the runtime's thread pool and returns the model immediately. When `fn` finishes, the runtime posts an `AsyncResult` event with the matching tag back through `update`.

```python
from plushie_pad import experiments as pad_experiments


def _write_experiment(path: str, source: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(source)
    return path


case EffectResult(tag="export", result=FileSaved(path=p)):
    return replace(model, status="Exporting..."), Command.task(
        lambda: _write_experiment(p, model.editor_source),
        "export_write",
    )

case AsyncResult(tag="export_write", value=path):
    if isinstance(path, Exception):
        return replace(model, status=f"Export failed: {path}")
    return replace(model, status=f"Exported to {path}")
```

Three things to notice:

- `fn` takes no arguments. Capture what it needs through a closure or a `functools.partial`.
- The return value arrives in `AsyncResult.value`. It can be anything picklable by memory, including a tuple or a dict.
- Exceptions become values. If `fn` raises, the runtime stores the exception object in `AsyncResult.value` and posts the event normally. Check with `isinstance(value, Exception)`. No try/except inside `fn` is required unless you want to wrap the error yourself.

`tag` identifies the task. Only one task per tag runs at a time. If `update` issues a new `Command.task` with a tag that already has a running task, the previous task is cancelled and its result is discarded.

### Task cancellation

`Command.cancel(tag)` stops a running task or stream:

```python
case Click(id="cancel-export"):
    return replace(model, status="Cancelling..."), Command.cancel("export_write")
```

Python threads cannot be force-killed safely, so cancellation means "stop delivering results". The thread keeps running until `fn` returns, but any `AsyncResult` or `StreamChunk` it produces after cancellation is silently dropped. For truly long work (network loops, large file processing), have `fn` poll a flag or use a generator so it can exit cooperatively.

## Command.stream: progressive results

Some background work produces intermediate values. Parsing a long file, running a linter, watching an external process: all want to surface progress as it happens. `Command.stream(fn, tag)` calls `fn` with an `emit` callback. Each `emit(value)` becomes a `StreamChunk(tag=..., value=...)` event. The function's return value becomes a final `AsyncResult` with the same tag.

```python
import subprocess


def _run_linter(source: str):
    def body(emit):
        proc = subprocess.Popen(
            ["ruff", "check", "--stdin-filename", "experiment.py", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        proc.stdin.write(source)
        proc.stdin.close()
        for line in proc.stdout:
            emit({"kind": "line", "text": line.rstrip()})
        return proc.wait()

    return Command.stream(body, "lint")
```

`update` handles the chunks and the final result:

```python
case Click(id="lint"):
    return replace(model, lint_lines=(), linting=True), _run_linter(model.editor_source)

case StreamChunk(tag="lint", value=chunk):
    lines = (*model.lint_lines, chunk["text"])
    return replace(model, lint_lines=lines)

case AsyncResult(tag="lint", value=exit_code):
    return replace(model, linting=False, lint_exit=exit_code)
```

Stream semantics mirror tasks: one stream per tag, superseding a new stream cancels the old one, `Command.cancel(tag)` stops delivery. Exceptions raised inside `fn` still arrive as the final `AsyncResult` with an exception value; already-emitted chunks are kept.

## Command.send_after: one-shot delays

For a single delayed event, use `Command.send_after(delay_ms, event)`:

```python
case AsyncResult(tag="export_write"):
    cleared = Command.send_after(3000, _ClearStatus())
    return replace(model, status="Exported"), cleared

case _ClearStatus():
    return replace(model, status="")
```

`event` is any Python value. When the timer fires, the runtime posts it straight through `update` without interpretation. A common pattern is to define a small private event class (or use a plain string constant) the way `_ClearStatus` is used above.

`send_after` is distinct from `Subscription.every`:

- `send_after` fires once and forgets.
- `Subscription.every` fires repeatedly as long as the subscription is returned from `subscribe`.

Use `send_after` for "flash this status for three seconds" or "retry once after a pause". Use `Subscription.every` for autosave ticks, clocks, and polling loops (chapter 10).

## Platform effects

Effects are commands that ask the renderer, not Python, to do something: show a file dialog, read the clipboard, post a desktop notification. They live in `plushie.effects`.

Every effect function takes a tag as its first argument and returns a `Command`. Dispatch it like any other command. The response arrives as `EffectResult(tag=..., result=<typed dataclass>)`.

### File dialogs

```python
from plushie import effects


case Click(id="import"):
    cmd = effects.file_open(
        "import",
        title="Import experiment",
        filters=[("Python", "*.py")],
    )
    return model, cmd

case Click(id="export"):
    cmd = effects.file_save(
        "export",
        title="Export experiment",
        default_name=f"{model.selected or 'experiment'}.py",
        filters=[("Python", "*.py")],
    )
    return model, cmd
```

The typed result tells you what happened:

```python
case EffectResult(tag="import", result=FileOpened(path=p)):
    return model, Command.task(lambda: _read_file(p), "import_read")

case EffectResult(tag="export", result=FileSaved(path=p)):
    return model, Command.task(
        lambda: _write_experiment(p, model.editor_source),
        "export_write",
    )

case EffectResult(tag=tag, result=EffectCancelled()):
    return replace(model, status=f"{tag} cancelled")
```

`EffectCancelled` means the user dismissed the dialog. That is a normal outcome, not an error. The full result taxonomy (`FileOpened`, `FilesOpened`, `FileSaved`, `DirectorySelected`, `ClipboardText`, `ClipboardWritten`, `NotificationShown`, `EffectCancelled`, `EffectTimeout`, `EffectError`, `EffectUnsupported`, `RendererRestarted`) is listed in the [Events reference](../reference/events.md).

Notice the pattern: the dialog returns a path; writing the file is a separate `Command.task`. Effects produce values; tasks do Python work with them. Keeping the two separated means every piece stays testable and each step's failure mode is explicit.

### Clipboard

```python
case Click(id="copy"):
    return model, effects.clipboard_write("copy", model.editor_source)

case EffectResult(tag="copy", result=ClipboardWritten()):
    return replace(model, status="Copied to clipboard"), Command.send_after(
        2000, _ClearStatus()
    )
```

`effects.clipboard_read(tag)` returns `ClipboardText(text=...)`. On Linux, `clipboard_read_primary` / `clipboard_write_primary` target the middle-click selection buffer. See the [Commands reference](../reference/commands.md) for the full surface.

### Notifications

```python
case AsyncResult(tag="export_write", value=path) if not isinstance(path, Exception):
    return model, effects.notification(
        "exported",
        "Plushie Pad",
        f"Experiment saved to {path}",
        urgency="low",
    )
```

On macOS, notifications may require the app to be bundled or have notification entitlements configured to appear.

### Tag-based correlation

Every effect and every task carries a tag. The tag is how `update` tells responses apart:

```python
case EffectResult(tag="import", result=FileOpened(path=p)):
    ...
case EffectResult(tag="paste", result=ClipboardText(text=t)):
    ...
```

Tags are plain strings. Pick names that describe intent (`"import"`, `"export"`, `"lint"`), not wire-level detail (`"req_42"`). No request IDs to store in the model, no pending-request table to maintain. The runtime already keeps that bookkeeping, keyed by tag.

### Default timeouts

Effects have built-in timeouts. File dialogs get two minutes (the user might be browsing); clipboard and notifications get five seconds. If the renderer does not respond in time, the result is `EffectTimeout()`:

```python
case EffectResult(tag="copy", result=EffectTimeout()):
    return replace(model, status="Clipboard timed out")
```

The defaults live in `plushie.effects.DEFAULT_TIMEOUTS` and can be inspected via `plushie.effects.default_timeout(kind)`.

## Putting it together in the pad

With import, export, copy, and lint, the toolbar grows:

```python
def _toolbar(model):
    return ui.row(
        ui.button("save", "Save" + (" *" if model.dirty else "")),
        ui.button("import", "Import"),
        ui.button("export", "Export", style="secondary"),
        ui.button("copy", "Copy"),
        ui.button("lint", "Lint"),
        ui.button("autosave", "Autosave: On" if model.autosave else "Autosave: Off"),
        padding=8,
        spacing=8,
    )
```

The model picks up fields for each new capability:

```python
@dataclass(frozen=True, slots=True)
class Model:
    # ... existing fields
    status: str = ""
    lint_lines: tuple[str, ...] = ()
    linting: bool = False
    lint_exit: int | None = None
```

And the `update` arms compose the pieces we've covered: an `effects.file_open` / `effects.file_save` to pick a path, a `Command.task` to do the actual I/O, an `AsyncResult` arm to surface the outcome, a `Command.send_after` to clear the status banner, and `Command.stream` for the linter. Each arm does one thing, returns cleanly, and lets the runtime orchestrate the rest.

A trimmed view of the wiring:

```python
case Click(id="import"):
    return model, effects.file_open(
        "import",
        title="Import experiment",
        filters=[("Python", "*.py")],
    )

case EffectResult(tag="import", result=FileOpened(path=p)):
    return model, Command.task(lambda: _read_file(p), "import_read")

case AsyncResult(tag="import_read", value=source):
    if isinstance(source, Exception):
        return replace(model, status=f"Import failed: {source}")
    return replace(
        model,
        editor_source=source,
        last_saved_source=source,
        dirty=False,
    )

case Click(id="copy"):
    return model, effects.clipboard_write("copy", model.editor_source)

case EffectResult(tag="copy", result=ClipboardWritten()):
    return replace(model, status="Copied"), Command.send_after(
        2000, _ClearStatus()
    )
```

The wiring is repetitive on purpose. Every path through the event flow is visible in one place, `update`, and nothing hides in callbacks or futures. If something goes wrong, the failing branch is where you look.

## Try it

Drop these into the pad (or a fresh experiment) and watch how the runtime handles each piece:

- Add a "Slow save" button that uses `Command.task` with `time.sleep(2)` before writing. Flip a `saving` flag to disable the button while the task runs.
- Make the linter cancellable with `Command.cancel("lint")` and verify that chunks stop arriving immediately after the click.
- Trigger `effects.notification` on export success and watch for `NotificationShown` or `EffectUnsupported` depending on your platform.
- Reduce an effect timeout by calling a clipboard effect while the renderer is paused (for example in a debugger) and handle the `EffectTimeout` result.

In the next chapter we leave toolbars behind and draw. Canvas is Plushie's retained-mode 2D surface: shapes, transforms, and hit-testable regions, with the same tree-diffing model you already know.

---

Next: [Canvas](12-canvas.md)
