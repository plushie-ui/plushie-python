# Effects

Effects are native platform operations that require the renderer to interact
with the OS on behalf of the host. File dialogs, clipboard access,
notifications, and similar features are effects.

## Design principle

Effects are simple request/response pairs over the same stdio transport.
Python asks, the renderer does, the renderer replies. No capability model,
no policy engine, no permission framework. If an effect is requested, the
renderer executes it.

If granular permission control is needed later, it can be layered in the
Python runtime (decide whether to send the request) rather than in the
renderer (decide whether to execute it). Keep the renderer dumb.

## How effects work

### Python side

<!-- test: test_file_open, test_effect_id_extractable, test_effect_id_auto_generated, test_all_effects_return_command_type -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie import effects
from plushie.events import Click, EffectResult

def update(self, model, event):
    match event:
        case Click(id="open_file"):
            cmd = effects.file_open(
                title="Choose a file",
                filters=[("Text files", "*.txt"), ("All files", "*")],
            )
            return model, cmd

        case EffectResult(status="ok", result={"path": path}):
            return replace(model, file_path=path)

        case EffectResult(status="error"):
            return model
```

Every effect function returns a `Command` dataclass. The command must be
returned from `update` as part of a `(model, command)` tuple -- discarding
it silently does nothing. The effect ID is auto-generated (e.g. `"ef_1"`)
and embedded in the command payload. You can extract it via
`cmd.payload["id"]` if you need to correlate a specific response.

Result keys come from the renderer as string keys (e.g.
`{"path": path}`, not attribute access).

The result arrives as an `EffectResult(request_id=id, status=status, ...)`
event in a subsequent `update` call. Effects are asynchronous -- the model
is not blocked waiting for the result.

### Transport

MessagePack is the default wire format. JSON shown here for readability
(use `--json` flag for JSONL mode).

```json
-> {"type": "effect", "id": "ef_1", "kind": "file_open", "payload": {"title": "Choose a file", "filters": [["Text files", "*.txt"], ["All files", "*"]]}}
<- {"type": "effect_response", "id": "ef_1", "status": "ok", "result": {"path": "/home/user/notes.txt"}}
```

The `id` correlates request to response. The runtime generates unique IDs
automatically.

## Available effects (v1)

| Kind | Description | Payload | Result |
|---|---|---|---|
| `file_open` | Open file dialog | `title`, `filters`, `directory` | `{path}` or error |
| `file_open_multiple` | Multi-file open dialog | `title`, `filters`, `directory` | `{paths}` or error |
| `file_save` | Save file dialog | `title`, `filters`, `default_name` | `{path}` or error |
| `directory_select` | Directory picker | `title` | `{path}` or error |
| `directory_select_multiple` | Multi-directory picker | `title` | `{paths}` or error |
| `clipboard_read` | Read clipboard | -- | `{text}` or error |
| `clipboard_write` | Write to clipboard | `text` | ok or error |
| `clipboard_read_html` | Read HTML from clipboard | -- | `{html}` or error |
| `clipboard_write_html` | Write HTML to clipboard | `html`, `alt_text` | ok or error |
| `clipboard_clear` | Clear the clipboard | -- | ok or error |
| `clipboard_read_primary` | Read primary selection (Linux) | -- | `{text}` or error |
| `clipboard_write_primary` | Write to primary selection (Linux) | `text` | ok or error |
| `notification` | Show OS notification | `title`, `body`, `icon`, `timeout`, `urgency`, `sound` | ok |

All effects can return `{"status": "error", "error": "unsupported"}` if the
renderer is running on a platform that does not support the operation.

### File dialogs

<!-- test: test_file_open, test_file_open_with_directory, test_file_open_multiple, test_file_save, test_directory_select, test_directory_select_multiple -- keep this code block in sync with the test -->
```python
from plushie import effects

# Single file open
effects.file_open(
    title="Open Project",
    directory="/home/user/projects",
    filters=[("Python", "*.py"), ("All files", "*")],
)

# Multiple file open
effects.file_open_multiple(
    title="Select images",
    filters=[("Images", "*.png"), ("JPEG", "*.jpg")],
)

# Save file
effects.file_save(
    title="Save As",
    default_name="untitled.txt",
    filters=[("Text files", "*.txt")],
)

# Directory picker
effects.directory_select(title="Choose output directory")

# Multiple directory picker
effects.directory_select_multiple(title="Select folders")
```

### Clipboard

<!-- test: test_clipboard_read, test_clipboard_write, test_clipboard_read_html, test_clipboard_write_html, test_clipboard_clear, test_clipboard_read_primary, test_clipboard_write_primary -- keep this code block in sync with the test -->
```python
from plushie import effects

# Read/write plain text
effects.clipboard_read()
effects.clipboard_write("Hello, clipboard")

# Read/write HTML
effects.clipboard_read_html()
effects.clipboard_write_html("<b>Bold</b>", alt_text="Bold")

# Clear
effects.clipboard_clear()

# Primary selection (Linux middle-click paste)
effects.clipboard_read_primary()
effects.clipboard_write_primary("Selected text")
```

### Notifications

<!-- test: test_notification -- keep this code block in sync with the test -->
```python
from plushie import effects

effects.notification(
    "Build Complete",
    "Your project compiled successfully.",
    icon="dialog-information",
    timeout=5000,
    urgency="normal",
    sound="complete",
)
```

## Adding new effects

Adding an effect requires changes in two places:

1. **Renderer:** handle the new `kind` in the effect dispatch, execute the
   platform operation, return the result.
2. **Python:** add a convenience function in `plushie.effects` (optional,
   apps can always send raw requests via `effects.request()`).

The transport does not need to change. Unknown effect kinds return
`unsupported`.

### Raw requests

For effects not yet wrapped in a convenience function, use the generic
`request()` function:

<!-- test: test_raw_request -- keep this code block in sync with the test -->
```python
from plushie import effects

cmd = effects.request("some_new_effect", foo="bar", baz=42)
```

## Effects are not commands

Some frameworks conflate effects (I/O operations) with commands (internal
state mutations). In plushie, `update` handles state mutations synchronously.
Effects handle I/O asynchronously. They are separate concerns with separate
code paths.

If your app needs something that is purely internal (start a timer, schedule
a follow-up event, batch multiple updates), that is handled in the Python
runtime, not as an effect. Effects always involve the renderer or the OS.
