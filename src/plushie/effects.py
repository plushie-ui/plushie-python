"""Platform effect requests (file dialogs, clipboard, notifications).

Effects are asynchronous I/O operations that require the renderer to
interact with the OS on behalf of the Python app. Each function takes
a ``tag`` as the first argument and returns a ``Command`` struct.
Dispatch it from ``update()`` like any other command. The result
arrives later as an ``EffectResult`` event. Pattern match on the tag
to identify which effect the response belongs to.

Only one effect per tag can be in flight at a time. Starting a new
effect with a tag that already has a pending request discards the
previous one.

Usage::

    from plushie import effects
    from plushie.events import EffectCancelled, FileOpened

    def update(self, model, event):
        match event:
            case Click(id="open"):
                return replace(model), effects.file_open("import", title="Pick a file")
            case EffectResult(tag="import", result=FileOpened(path=p)):
                return replace(model, file=p)
            case EffectResult(tag="import", result=EffectCancelled()):
                return model

Timeouts: each effect has a default timeout. If the renderer does not
respond in time, ``EffectResult(tag=tag, result=EffectTimeout())``
arrives in ``update()``.
"""

from __future__ import annotations

import threading
from typing import Any

from plushie.commands import Command

# Thread-safe auto-incrementing counter for internal wire IDs.
_counter_lock = threading.Lock()
_counter = 0


def _generate_wire_id() -> str:
    """Generate a unique internal wire ID for renderer correlation."""
    global _counter
    with _counter_lock:
        _counter += 1
        return f"ef_{_counter}"


def _reset_counter() -> None:
    """Reset the ID counter. For testing only."""
    global _counter
    with _counter_lock:
        _counter = 0


# Default timeouts per effect kind (milliseconds).
DEFAULT_TIMEOUTS: dict[str, int] = {
    "file_open": 120_000,
    "file_open_multiple": 120_000,
    "file_save": 120_000,
    "directory_select": 120_000,
    "directory_select_multiple": 120_000,
    "clipboard_read": 5_000,
    "clipboard_write": 5_000,
    "clipboard_read_html": 5_000,
    "clipboard_write_html": 5_000,
    "clipboard_clear": 5_000,
    "clipboard_read_primary": 5_000,
    "clipboard_write_primary": 5_000,
    "notification": 5_000,
}


def request(tag: str, kind: str, **opts: Any) -> Command:
    """Generic effect request. Returns a command struct.

    Args:
        tag: Identifies this effect in the ``EffectResult`` event.
        kind: Effect type (e.g. ``"file_open"``, ``"clipboard_read"``).
        **opts: Effect-specific payload parameters.
    """
    wire_id = _generate_wire_id()
    return Command(
        type="effect",
        payload={"id": wire_id, "tag": tag, "kind": kind, "opts": opts},
    )


# ------------------------------------------------------------------
# File dialogs
# ------------------------------------------------------------------


def file_open(
    tag: str,
    /,
    *,
    title: str | None = None,
    directory: str | None = None,
    filters: list[tuple[str, str]] | None = None,
    default_name: str | None = None,
) -> Command:
    """Open-file dialog. Returns a command.

    Args:
        tag: Effect tag for result matching.
        title: Dialog title.
        directory: Starting directory path.
        filters: List of ``(label, pattern)`` tuples.
        default_name: Default file name.
    """
    opts: dict[str, Any] = {}
    if title is not None:
        opts["title"] = title
    if directory is not None:
        opts["directory"] = directory
    if filters is not None:
        opts["filters"] = filters
    if default_name is not None:
        opts["default_name"] = default_name
    return request(tag, "file_open", **opts)


def file_open_multiple(
    tag: str,
    /,
    *,
    title: str | None = None,
    directory: str | None = None,
    filters: list[tuple[str, str]] | None = None,
) -> Command:
    """Multi-file open dialog. Returns a command."""
    opts: dict[str, Any] = {}
    if title is not None:
        opts["title"] = title
    if directory is not None:
        opts["directory"] = directory
    if filters is not None:
        opts["filters"] = filters
    return request(tag, "file_open_multiple", **opts)


def file_save(
    tag: str,
    /,
    *,
    title: str | None = None,
    directory: str | None = None,
    filters: list[tuple[str, str]] | None = None,
    default_name: str | None = None,
) -> Command:
    """Save-file dialog. Returns a command."""
    opts: dict[str, Any] = {}
    if title is not None:
        opts["title"] = title
    if directory is not None:
        opts["directory"] = directory
    if filters is not None:
        opts["filters"] = filters
    if default_name is not None:
        opts["default_name"] = default_name
    return request(tag, "file_save", **opts)


def directory_select(
    tag: str,
    /,
    *,
    title: str | None = None,
    directory: str | None = None,
) -> Command:
    """Directory picker. Returns a command."""
    opts: dict[str, Any] = {}
    if title is not None:
        opts["title"] = title
    if directory is not None:
        opts["directory"] = directory
    return request(tag, "directory_select", **opts)


def directory_select_multiple(
    tag: str,
    /,
    *,
    title: str | None = None,
    directory: str | None = None,
) -> Command:
    """Multi-directory picker. Returns a command."""
    opts: dict[str, Any] = {}
    if title is not None:
        opts["title"] = title
    if directory is not None:
        opts["directory"] = directory
    return request(tag, "directory_select_multiple", **opts)


# ------------------------------------------------------------------
# Clipboard
# ------------------------------------------------------------------


def clipboard_read(tag: str, /) -> Command:
    """Read clipboard contents. Returns a command."""
    return request(tag, "clipboard_read")


def clipboard_write(tag: str, text: str, /) -> Command:
    """Write *text* to the clipboard. Returns a command."""
    return request(tag, "clipboard_write", text=text)


def clipboard_read_html(tag: str, /) -> Command:
    """Read HTML content from the clipboard. Returns a command."""
    return request(tag, "clipboard_read_html")


def clipboard_write_html(
    tag: str, html: str, /, alt_text: str | None = None
) -> Command:
    """Write HTML content to the clipboard. Returns a command."""
    opts: dict[str, Any] = {"html": html}
    if alt_text is not None:
        opts["alt_text"] = alt_text
    return request(tag, "clipboard_write_html", **opts)


def clipboard_clear(tag: str, /) -> Command:
    """Clear the clipboard. Returns a command."""
    return request(tag, "clipboard_clear")


def clipboard_read_primary(tag: str, /) -> Command:
    """Read primary clipboard (middle-click paste on Linux). Returns a command."""
    return request(tag, "clipboard_read_primary")


def clipboard_write_primary(tag: str, text: str, /) -> Command:
    """Write *text* to the primary clipboard. Returns a command."""
    return request(tag, "clipboard_write_primary", text=text)


# ------------------------------------------------------------------
# Notifications
# ------------------------------------------------------------------


def notification(
    tag: str,
    title: str,
    body: str,
    /,
    *,
    icon: str | None = None,
    timeout: int | None = None,
    urgency: str | None = None,
    sound: str | None = None,
) -> Command:
    """Show an OS notification. Returns a command.

    On macOS, notifications may require the app to be bundled (.app)
    or have notification entitlements to display.

    Args:
        tag: Effect tag for result matching.
        title: Notification title.
        body: Notification body text.
        icon: Icon name or path.
        timeout: Auto-dismiss timeout in milliseconds.
        urgency: ``"low"``, ``"normal"``, or ``"critical"``.
        sound: Sound name to play.
    """
    opts: dict[str, Any] = {"title": title, "body": body}
    if icon is not None:
        opts["icon"] = icon
    if timeout is not None:
        opts["timeout"] = timeout
    if urgency is not None:
        opts["urgency"] = urgency
    if sound is not None:
        opts["sound"] = sound
    return request(tag, "notification", **opts)


def default_timeout(kind: str) -> int | None:
    """Return the default timeout in ms for *kind*, or ``None`` if unknown."""
    return DEFAULT_TIMEOUTS.get(kind)


__all__ = [
    "clipboard_clear",
    "clipboard_read",
    "clipboard_read_html",
    "clipboard_read_primary",
    "clipboard_write",
    "clipboard_write_html",
    "clipboard_write_primary",
    "default_timeout",
    "directory_select",
    "directory_select_multiple",
    "file_open",
    "file_open_multiple",
    "file_save",
    "notification",
    "request",
]
