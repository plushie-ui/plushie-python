"""Test fixture for driving plushie applications synchronously.

``AppFixture`` wraps an application class and a ``SessionPool`` session,
providing a synchronous interaction API for pytest tests.  All command
processing happens immediately (no threads, no event loop) so tests
are deterministic and fast.

Usage::

    from plushie.testing import AppFixture

    def test_counter(plushie_pool):
        with AppFixture(Counter, plushie_pool) as app:
            assert app.model.count == 0
            app.click("#inc")
            assert app.model.count == 1
            assert app.text("#count") == "Count: 1"
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from plushie.app import App, AppBuilder
from plushie.commands import Command
from plushie.events import AsyncResult, StreamChunk
from plushie.protocol import encode_selector
from plushie.testing.element import Element, ElementNotFoundError
from plushie.testing.pool import SessionPool
from plushie.tree import Node, diff, normalize_view, text_of

logger = logging.getLogger("plushie.testing")

_MAX_COMMAND_DEPTH: int = 100
"""Safety limit to prevent infinite command loops."""


# ---------------------------------------------------------------------------
# Synchronous command processor
# ---------------------------------------------------------------------------


def _unwrap_update(
    result: Any,
) -> tuple[Any, list[Command]]:
    """Normalize an update/init return value to (model, commands)."""
    if isinstance(result, tuple) and len(result) == 2:
        model, cmds = result
        if isinstance(cmds, Command):
            return model, [cmds]
        if isinstance(cmds, list):
            return model, cmds
        return model, []
    return result, []


def _process_commands(
    app: App[Any],
    model: Any,
    commands: list[Command],
    depth: int = 0,
) -> Any:
    """Execute commands synchronously, threading model state through each dispatch.

    task/stream/done are executed immediately. batch recurses.
    Widget ops, window ops, timers, effects, cancel are skipped
    (they need a live renderer).

    Args:
        app: The application instance.
        model: Current model state.
        commands: Commands to process.
        depth: Current recursion depth (safety limit).

    Returns:
        The final model after all command-driven updates.
    """
    if depth > _MAX_COMMAND_DEPTH:
        return model

    for cmd in commands:
        t = cmd.type
        p = cmd.payload

        if t == "none":
            continue

        if t == "batch":
            model = _process_commands(app, model, p.get("commands", []), depth + 1)
            continue

        if t == "task":
            fn = p["fn"]
            tag = p["tag"]
            result = fn()
            event = AsyncResult(tag=tag, value=result)
            new_model, new_cmds = _unwrap_update(app.update(model, event))
            model = _process_commands(app, new_model, new_cmds, depth + 1)
            continue

        if t == "stream":
            fn = p["fn"]
            tag = p["tag"]
            chunks: list[Any] = []

            def emit(value: Any, _chunks: list[Any] = chunks) -> None:
                _chunks.append(value)

            final = fn(emit)

            # Process each emitted chunk
            for chunk_val in chunks:
                event = StreamChunk(tag=tag, value=chunk_val)
                new_model, new_cmds = _unwrap_update(app.update(model, event))
                model = _process_commands(app, new_model, new_cmds, depth + 1)

            # Process final result
            event = AsyncResult(tag=tag, value=final)
            new_model, new_cmds = _unwrap_update(app.update(model, event))
            model = _process_commands(app, new_model, new_cmds, depth + 1)
            continue

        if t == "done":
            mapper = p["mapper"]
            value = p["value"]
            event = mapper(value)
            new_model, new_cmds = _unwrap_update(app.update(model, event))
            model = _process_commands(app, new_model, new_cmds, depth + 1)
            continue

        # Everything else (widget_op, window_op, effect, send_after,
        # cancel, exit, image_op, extension_command, advance_frame)
        # is silently skipped in test mode.

    return model


# ---------------------------------------------------------------------------
# Selector resolution
# ---------------------------------------------------------------------------


def _parse_id_selector(selector: str) -> tuple[str | None, str] | None:
    if not selector.startswith("#"):
        return None

    raw = selector[1:]
    if "::" in raw:
        window_id, widget_id = raw.split("::", 1)
        return window_id, widget_id

    return None, raw


def _resolve_selector(selector: str, tree: Node | None) -> dict[str, str]:
    """Resolve a user selector to a wire selector dict.

    For ``#id`` selectors without a ``/``, looks up the full scoped ID
    in the local tree so the renderer can find it by exact match.

    Args:
        selector: User-facing selector string.
        tree: The current normalized tree (for local ID lookup).

    Returns:
        Wire selector dict.
    """
    parsed = _parse_id_selector(selector)
    if parsed is not None:
        window_id, target_id = parsed
        if tree is not None:
            exact_matches = _find_exact_id_targets(tree, target_id)
            if window_id is not None:
                exact_matches = [
                    match for match in exact_matches if match["window_id"] == window_id
                ]
            if len(exact_matches) == 1:
                match = exact_matches[0]
                return {
                    "by": "id",
                    "value": match["id"],
                    "window_id": match["window_id"],
                }
            if "/" not in target_id:
                local_matches = _find_local_id_targets(tree, target_id)
                if window_id is not None:
                    local_matches = [
                        match
                        for match in local_matches
                        if match["window_id"] == window_id
                    ]
                if len(local_matches) == 1:
                    match = local_matches[0]
                    return {
                        "by": "id",
                        "value": match["id"],
                        "window_id": match["window_id"],
                    }
                if len(local_matches) > 1:
                    raise ValueError(
                        f'selector "{selector}" is ambiguous across windows; prefix it with "#<window_id>::" or use the full scoped id'
                    )
                if not local_matches and not exact_matches:
                    available = _collect_widget_ids(tree)
                    hint = (
                        f" Available IDs: {', '.join(sorted(available))}"
                        if available
                        else ""
                    )
                    raise ValueError(f'widget not found: "{selector}".{hint}')
            elif len(exact_matches) > 1:
                raise ValueError(
                    f'selector "{selector}" matches multiple windows; prefix it with "#<window_id>::"'
                )
            elif not exact_matches:
                available = _collect_widget_ids(tree)
                hint = (
                    f" Available IDs: {', '.join(sorted(available))}"
                    if available
                    else ""
                )
                raise ValueError(f'widget not found: "{selector}".{hint}')

        result = {"by": "id", "value": target_id}
        if window_id is not None:
            result["window_id"] = window_id
        return result
    return encode_selector(selector)


def _find_exact_id_targets(
    tree: Node,
    target_id: str,
    current_window_id: str | None = None,
) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    node_window_id = tree["id"] if tree.get("type") == "window" else current_window_id
    if node_window_id is not None and tree.get("id") == target_id:
        matches.append({"id": tree["id"], "window_id": node_window_id})
    for child in tree.get("children", []):
        matches.extend(_find_exact_id_targets(child, target_id, node_window_id))
    return matches


def _find_local_id_targets(
    tree: Node,
    target_id: str,
    current_window_id: str | None = None,
) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    node_window_id = tree["id"] if tree.get("type") == "window" else current_window_id
    local_id = tree["id"].rsplit("/", 1)[-1]
    if node_window_id is not None and local_id == target_id:
        matches.append({"id": tree["id"], "window_id": node_window_id})
    for child in tree.get("children", []):
        matches.extend(_find_local_id_targets(child, target_id, node_window_id))
    return matches


def _collect_widget_ids(tree: Node) -> set[str]:
    """Collect all non-auto widget IDs from the tree for error messages."""
    ids: set[str] = set()
    node_id = tree.get("id", "")
    if node_id and not node_id.startswith("auto:"):
        ids.add(node_id.rsplit("/", 1)[-1])
    for child in tree.get("children", []):
        if isinstance(child, dict):
            ids.update(_collect_widget_ids(child))
    return ids


def _find_node_by_id(tree: Node, target_id: str) -> Node | None:
    if tree.get("id") == target_id:
        return tree
    for child in tree.get("children", []):
        found = _find_node_by_id(child, target_id)
        if found is not None:
            return found
    return None


def _find_node_by_selector(tree: Node, selector: str) -> Node | None:
    resolved = _resolve_selector(selector, tree)
    if resolved.get("by") != "id":
        return None

    target_id = resolved.get("value")
    if not isinstance(target_id, str):
        return None

    return _find_node_by_id(tree, target_id)


def _build_key_lookup() -> dict[str, str]:
    """Build a lowercase -> PascalCase lookup from the keys module.

    Single-character keys are excluded since they pass through as
    lowercase directly.
    """
    from plushie import keys as _keys

    lookup: dict[str, str] = {}
    for name in dir(_keys):
        if name.startswith("_"):
            continue
        val = getattr(_keys, name)
        if isinstance(val, str) and len(val) > 1:
            lookup[val.lower()] = val
    return lookup


_NAMED_KEY_LOOKUP: dict[str, str] = _build_key_lookup()


def _resolve_key_name(key_name: str) -> str:
    """Resolve a key name to its canonical PascalCase form.

    Single-character keys are lowercased (matching iced's logical key
    format). Multi-character named keys are resolved case-insensitively
    against the full key constant set.

    Raises:
        ValueError: If a multi-character key name is not recognized.
    """
    if len(key_name) == 1:
        return key_name.lower()

    resolved = _NAMED_KEY_LOOKUP.get(key_name.lower())
    if resolved is not None:
        return resolved

    raise ValueError(
        f"unknown key {key_name!r}. "
        "Examples: Tab, ArrowRight, PageUp, Escape, Enter. "
        "See plushie.keys for the full list"
    )


def _parse_key(key: str) -> dict[str, Any]:
    """Parse a key string like ``"ctrl+s"`` into key + modifiers dict.

    Key names are resolved case-insensitively: ``"escape"``, ``"Escape"``,
    and ``"ESCAPE"`` all produce ``"Escape"``. Single-character keys are
    lowercased (matching iced's logical key format).
    """
    parts = key.split("+")
    key_name = parts[-1]
    mod_parts = parts[:-1]

    modifiers: dict[str, bool] = {}
    for mod in mod_parts:
        mod_lower = mod.lower()
        if mod_lower in ("ctrl", "shift", "alt", "logo", "command"):
            modifiers[mod_lower] = True

    resolved = _resolve_key_name(key_name)
    return {"key": resolved, "modifiers": modifiers}


# ---------------------------------------------------------------------------
# AppFixture
# ---------------------------------------------------------------------------


class AppFixture[M]:
    """Synchronous test fixture for a plushie application.

    Wraps an ``App`` instance and a ``SessionPool`` session, providing
    deterministic interaction methods that process commands immediately.

    Type parameter ``M`` is the application model type.

    Args:
        app_class: An ``App`` subclass (instantiated automatically) or
            an ``App``/``AppBuilder`` instance.
        pool: The ``SessionPool`` to use for renderer communication.
    """

    def __init__(
        self,
        app_class: type[App[M]] | App[M] | AppBuilder,
        pool: SessionPool,
    ) -> None:
        self._pool = pool

        # Instantiate the app
        app: App[Any]
        if isinstance(app_class, AppBuilder):
            app = app_class.build()
        elif isinstance(app_class, type):
            app = app_class()
        else:
            app = app_class
        self._app: App[Any] = app

        # Register a session
        self._session_id = pool.register()

        # Initialize
        raw = app.init()
        model, commands = _unwrap_update(raw)
        model = _process_commands(app, model, commands)
        self._model: Any = model

        # Render initial tree
        tree = self._render()
        self._tree: Node | None = tree

        # Send settings + snapshot to renderer
        app_settings = {}
        try:
            app_settings = app.settings()
        except Exception:
            logger.debug("app.settings() raised during fixture init", exc_info=True)

        pool.send_settings(self._session_id, app_settings)

        if tree is not None:
            pool.send_snapshot(self._session_id, tree)

    # -------------------------------------------------------------------
    # Context manager
    # -------------------------------------------------------------------

    def __enter__(self) -> AppFixture[M]:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Release the session back to the pool."""
        if self._session_id:
            try:
                self._pool.unregister(self._session_id)
            except Exception:
                logger.debug("unregister failed during close", exc_info=True)
            self._session_id = ""

    # -------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------

    @property
    def model(self) -> Any:
        """The current application model."""
        return self._model

    @property
    def tree(self) -> Node | None:
        """The current normalized UI tree."""
        return self._tree

    # -------------------------------------------------------------------
    # Interactions
    # -------------------------------------------------------------------

    def click(self, selector: str) -> None:
        """Click a widget.

        Args:
            selector: Widget selector (e.g. ``"#button_id"``).

        Raises:
            TypeError: If the target is a checkbox or toggler (use
                ``toggle()`` instead).
        """
        self._check_interaction_type(
            selector,
            "click",
            {"button"},
            {
                "checkbox": "toggle",
                "toggler": "toggle",
            },
        )
        self._interact("click", selector)

    def type_text(self, selector: str, text: str) -> None:
        """Type text into a text input or text editor.

        Args:
            selector: Widget selector.
            text: Text to type.

        Raises:
            TypeError: If the target is not a text input or editor.
        """
        self._check_interaction_type(
            selector,
            "type_text",
            {
                "text_input",
                "text_editor",
            },
        )
        self._interact("type_text", selector, payload={"text": text})

    def submit(self, selector: str) -> None:
        """Submit a text input (simulates pressing Enter).

        Reads the current value from the local tree to include in the
        interact payload.

        Args:
            selector: Widget selector.

        Raises:
            TypeError: If the target is not a text input.
        """
        self._check_interaction_type(selector, "submit", {"text_input"})
        value = self._read_widget_value(selector)
        self._interact("submit", selector, payload={"value": value})

    def toggle(self, selector: str) -> None:
        """Toggle a checkbox or toggler.

        Reads the current checked/toggled state from the local tree
        and inverts it.

        Args:
            selector: Widget selector.

        Raises:
            TypeError: If the target is not a checkbox or toggler (use
                ``click()`` for buttons).
        """
        self._check_interaction_type(
            selector,
            "toggle",
            {
                "checkbox",
                "toggler",
            },
            {
                "button": "click",
            },
        )
        value = self._read_toggle_value(selector)
        self._interact("toggle", selector, payload={"value": not value})

    def select(self, selector: str, value: Any) -> None:
        """Select a value from a pick_list, combo_box, or radio group.

        Args:
            selector: Widget selector.
            value: The value to select.
        """
        self._interact("select", selector, payload={"value": value})

    def slide(self, selector: str, value: float) -> None:
        """Slide a slider to the given value.

        Args:
            selector: Widget selector.
            value: Target value.
        """
        self._interact("slide", selector, payload={"value": value})

    def press(self, key: str) -> None:
        """Press a key (key down).

        Args:
            key: Key string, optionally with modifiers (e.g. ``"ctrl+s"``).
        """
        self._interact("press", None, payload=_parse_key(key))

    def release(self, key: str) -> None:
        """Release a key (key up).

        Args:
            key: Key string.
        """
        self._interact("release", None, payload=_parse_key(key))

    def type_key(self, key: str) -> None:
        """Type a key (press + release).

        Args:
            key: Key string.
        """
        self._interact("type_key", None, payload=_parse_key(key))

    def scroll(self, selector: str, delta_x: float = 0, delta_y: float = 0) -> None:
        """Scroll a widget.

        Args:
            selector: Widget selector.
            delta_x: Horizontal scroll delta.
            delta_y: Vertical scroll delta.
        """
        self._interact(
            "scroll", selector, payload={"delta_x": delta_x, "delta_y": delta_y}
        )

    def move_to(self, x: float, y: float) -> None:
        """Move the cursor to coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
        """
        self._interact("move_to", None, payload={"x": x, "y": y})

    def paste(self, selector: str, text: str) -> None:
        """Paste text into a widget.

        Args:
            selector: Widget selector.
            text: Text to paste.
        """
        self._interact("paste", selector, payload={"text": text})

    def sort(self, selector: str, column: str) -> None:
        """Sort a table column.

        Args:
            selector: Widget selector.
            column: Column identifier.
        """
        self._interact("sort", selector, payload={"column": column})

    def canvas_press(
        self, selector: str, x: float, y: float, button: str = "left"
    ) -> None:
        """Press on a canvas.

        Args:
            selector: Widget selector.
            x: X coordinate.
            y: Y coordinate.
            button: Mouse button.
        """
        self._interact(
            "canvas_press", selector, payload={"x": x, "y": y, "button": button}
        )

    def canvas_release(
        self, selector: str, x: float, y: float, button: str = "left"
    ) -> None:
        """Release on a canvas.

        Args:
            selector: Widget selector.
            x: X coordinate.
            y: Y coordinate.
            button: Mouse button.
        """
        self._interact(
            "canvas_release", selector, payload={"x": x, "y": y, "button": button}
        )

    def canvas_move(self, selector: str, x: float, y: float) -> None:
        """Move on a canvas.

        Args:
            selector: Widget selector.
            x: X coordinate.
            y: Y coordinate.
        """
        self._interact("canvas_move", selector, payload={"x": x, "y": y})

    def pane_focus_cycle(self, selector: str) -> None:
        """Cycle focus in a pane grid.

        Args:
            selector: Widget selector.
        """
        self._interact("pane_focus_cycle", selector)

    # -------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------

    def find(self, selector: str) -> Element:
        """Find an element by selector. Raises if not found.

        Args:
            selector: Widget selector.

        Returns:
            The matching ``Element``.

        Raises:
            ElementNotFoundError: If no matching element is found.
        """
        node = self._pool.query_find(self._session_id, selector)
        if node is None:
            available = _available_ids(self._tree)
            raise ElementNotFoundError(
                f"element not found: {selector!r}. Available IDs: {available}"
            )
        return Element(node=node)

    def query(self, selector: str) -> Element | None:
        """Find an element by selector. Returns ``None`` if not found.

        Args:
            selector: Widget selector.

        Returns:
            The matching ``Element``, or ``None``.
        """
        node = self._pool.query_find(self._session_id, selector)
        if node is None:
            return None
        return Element(node=node)

    def text(self, selector: str) -> str | None:
        """Extract display text from an element.

        Args:
            selector: Widget selector.

        Returns:
            The text content, or ``None`` if not found or no text.
        """
        # Try local tree first for speed
        if self._tree is not None:
            node = _find_node_by_selector(self._tree, selector)
            if node is not None:
                return text_of(node)
        # Fall back to renderer query
        el = self.query(selector)
        if el is None:
            return None
        return el.text()

    def exists(self, selector: str) -> bool:
        """Check whether an element exists in the tree.

        Args:
            selector: Widget selector.

        Returns:
            ``True`` if the element exists.
        """
        return self.query(selector) is not None

    def find_by_role(self, role: str) -> Element | None:
        """Find an element by its accessible role.

        Checks ``props.a11y.role`` first, then falls back to the
        widget type name (e.g. ``"button"`` matches buttons without
        an explicit a11y role).

        Args:
            role: The role string to search for.

        Returns:
            The first matching ``Element``, or ``None``.
        """
        sel = {"by": "role", "value": role}
        raw = self._pool.query_find(self._session_id, sel)
        if raw is None:
            return None
        return Element(node=raw)

    def find_by_label(self, label: str) -> Element | None:
        """Find an element by its accessible label.

        Checks ``props.a11y.label`` first, then falls back to
        ``props.label`` and ``props.content``.

        Args:
            label: The label text to search for.

        Returns:
            The first matching ``Element``, or ``None``.
        """
        sel = {"by": "label", "value": label}
        raw = self._pool.query_find(self._session_id, sel)
        if raw is None:
            return None
        return Element(node=raw)

    def find_focused(self) -> Element | None:
        """Find the currently focused element.

        Returns:
            The focused ``Element``, or ``None`` if nothing is focused.
        """
        sel = {"by": "focused"}
        raw = self._pool.query_find(self._session_id, sel)
        if raw is None:
            return None
        return Element(node=raw)

    # -------------------------------------------------------------------
    # Convenience assertions
    # -------------------------------------------------------------------

    def assert_text(self, selector: str, expected: str) -> None:
        """Assert that the text of the selected element matches ``expected``.

        Shows the actual text on failure so the caller doesn't have to
        dig for it.

        Args:
            selector: Widget selector.
            expected: The expected text string.

        Raises:
            AssertionError: If the element is not found or text differs.
        """
        actual = self.text(selector)
        if actual is None:
            available = _available_ids(self._tree)
            raise AssertionError(
                f"assert_text({selector!r}): element not found or has no text. "
                f"Available IDs: {available}"
            )
        if actual != expected:
            raise AssertionError(
                f"assert_text({selector!r}): expected {expected!r}, got {actual!r}"
            )

    def assert_exists(self, selector: str) -> None:
        """Assert that an element matching ``selector`` exists.

        Shows available IDs on failure to help diagnose typos.

        Args:
            selector: Widget selector.

        Raises:
            AssertionError: If the element is not found.
        """
        if not self.exists(selector):
            available = _available_ids(self._tree)
            raise AssertionError(
                f"assert_exists({selector!r}): element not found. "
                f"Available IDs: {available}"
            )

    def assert_not_exists(self, selector: str) -> None:
        """Assert that no element matches ``selector``.

        Args:
            selector: Widget selector.

        Raises:
            AssertionError: If the element exists.
        """
        if self.exists(selector):
            raise AssertionError(
                f"assert_not_exists({selector!r}): element unexpectedly exists"
            )

    def assert_model(self, expected: object) -> None:
        """Assert that the current model equals ``expected``.

        Shows the actual model on failure.

        Args:
            expected: The expected model value.

        Raises:
            AssertionError: If the model does not equal ``expected``.
        """
        actual = self._model
        if actual != expected:
            raise AssertionError(f"assert_model: expected {expected!r}, got {actual!r}")

    def save_screenshot(self, name: str) -> Path:
        """Save a screenshot PNG to ``test/screenshots/``.

        Requests a screenshot from the renderer and writes the raw
        PNG data to disk. Returns the path to the saved file.

        Args:
            name: Base name for the screenshot file (without extension).

        Returns:
            The ``Path`` to the saved PNG file.

        Raises:
            RuntimeError: If the backend does not return screenshot data.
        """
        resp = self._pool.screenshot(self._session_id, name)
        data = resp.get("data")
        if not data:
            raise RuntimeError(
                f"save_screenshot({name!r}): backend did not return screenshot data"
            )

        out_dir = Path("test") / "screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{name}.png"
        if isinstance(data, str):
            import base64

            out_path.write_bytes(base64.b64decode(data))
        else:
            out_path.write_bytes(data)
        return out_path

    # -------------------------------------------------------------------
    # Regression helpers
    # -------------------------------------------------------------------

    def assert_tree_hash(self, name: str) -> None:
        """Assert the tree hash matches the golden file.

        On first run, creates the golden file. On subsequent runs,
        compares hashes. Set ``PLUSHIE_UPDATE_SNAPSHOTS=1`` to
        force-update golden files.

        Args:
            name: Label for this hash capture.
        """
        resp = self._pool.tree_hash(self._session_id, name)
        actual_hash = resp.get("hash", "")

        golden_dir = Path("test") / "snapshots"
        golden_file = golden_dir / f"{name}.tree_hash"

        update = os.environ.get("PLUSHIE_UPDATE_SNAPSHOTS") == "1"

        if update or not golden_file.exists():
            golden_dir.mkdir(parents=True, exist_ok=True)
            golden_file.write_text(actual_hash)
            return

        expected_hash = golden_file.read_text().strip()
        if actual_hash != expected_hash:
            raise AssertionError(
                f"tree hash mismatch for {name!r}: "
                f"expected {expected_hash!r}, got {actual_hash!r}. "
                "Set PLUSHIE_UPDATE_SNAPSHOTS=1 to update."
            )

    def assert_screenshot(self, name: str) -> None:
        """Assert the screenshot hash matches the golden file.

        On first run, creates the golden file. On subsequent runs,
        compares hashes. Set ``PLUSHIE_UPDATE_SCREENSHOTS=1`` to
        force-update golden files.

        Args:
            name: Label for this screenshot capture.
        """
        resp = self._pool.screenshot(self._session_id, name)
        actual_hash = resp.get("hash", "")

        # Empty hash means the backend doesn't support pixel capture
        if not actual_hash:
            return

        golden_dir = Path("test") / "screenshots"
        golden_file = golden_dir / f"{name}.screenshot_hash"

        update = os.environ.get("PLUSHIE_UPDATE_SCREENSHOTS") == "1"

        if update or not golden_file.exists():
            golden_dir.mkdir(parents=True, exist_ok=True)
            golden_file.write_text(actual_hash)
            return

        expected_hash = golden_file.read_text().strip()
        if actual_hash != expected_hash:
            raise AssertionError(
                f"screenshot hash mismatch for {name!r}: "
                f"expected {expected_hash!r}, got {actual_hash!r}. "
                "Set PLUSHIE_UPDATE_SCREENSHOTS=1 to update."
            )

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    def reset(self) -> None:
        """Reset the fixture to initial state.

        Re-runs ``init()``, processes commands, re-renders, and sends
        a fresh snapshot to the renderer.
        """
        raw = self._app.init()
        model, commands = _unwrap_update(raw)
        model = _process_commands(self._app, model, commands)
        self._model = model

        tree = self._render()
        self._tree = tree

        if tree is not None:
            self._pool.send_snapshot(self._session_id, tree)

    def await_async(self) -> None:
        """No-op in synchronous test mode.

        Commands are processed synchronously, so async tasks have
        already completed by the time this is called.
        """

    # -------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------

    def _render(self) -> Node | None:
        """Call app.view() + normalize."""
        try:
            raw_tree = self._app.view(self._model)
            return normalize_view(raw_tree)
        except Exception:
            logger.exception("app.view() raised during render")
            return None

    def _interact(
        self,
        action: str,
        selector: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Core interaction method.

        Sends the interact message to the renderer, collects events,
        processes each through app.update(), processes resulting
        commands synchronously, re-renders, diffs, and sends patches.

        For headless mode, interact_step messages are handled
        transparently by the Connection's on_step callback.

        Args:
            action: Interaction type.
            selector: Widget selector (or None for global actions).
            payload: Action-specific parameters.
        """
        wire_sel: dict[str, str] | None = None
        if selector is not None:
            wire_sel = _resolve_selector(selector, self._tree)

        # Build the selector string for the Connection.interact call
        sel_str: str | None = None
        if wire_sel is not None:
            # Reconstruct a selector string from the wire dict
            by = wire_sel.get("by", "")
            value = wire_sel.get("value", "")
            if by == "id":
                sel_str = f"#{value}"
            elif by == "text":
                sel_str = value
            else:
                sel_str = value

        conn = self._pool._conn
        if conn is None:
            raise RuntimeError("session pool is not started")

        old_session = conn.session
        conn.session = self._session_id

        def on_step(step_events: list[Any]) -> dict[str, Any]:
            """Handle headless interact_step: process events, return updated tree."""
            for event in step_events:
                self._dispatch_event(event)
            tree = self._render()
            self._tree = tree
            return tree or {}

        try:
            events = conn.interact(
                action,
                sel_str,
                payload,
                on_step=on_step,
                timeout=30.0,
            )
        finally:
            conn.session = old_session

        # Process final events
        for event in events:
            self._dispatch_event(event)

        # Re-render and sync
        new_tree = self._render()
        if new_tree is not None:
            old_tree = self._tree
            if old_tree is None:
                self._pool.send_snapshot(self._session_id, new_tree)
            else:
                ops = diff(old_tree, new_tree)
                if ops:
                    self._pool.send_patch(self._session_id, ops)
        self._tree = new_tree

    def _dispatch_event(self, event: Any) -> None:
        """Process a single event through app.update + sync command processing."""
        if event is None or isinstance(event, dict):
            # Raw dict events we don't recognize -- skip
            return

        try:
            result = self._app.update(self._model, event)
        except Exception:
            logger.exception("app.update() raised during test interaction")
            return

        if result is None:
            return

        model, commands = _unwrap_update(result)
        model = _process_commands(self._app, model, commands)
        self._model = model

    def _read_widget_value(self, selector: str) -> str:
        """Read the current text value of a widget from the local tree."""
        if self._tree is None:
            return ""
        node = _find_node_by_selector(self._tree, selector)
        if node is None:
            return ""
        props = node.get("props", {})
        return str(props.get("value", ""))

    def _check_interaction_type(
        self,
        selector: str,
        action: str,
        allowed_types: set[str],
        suggestions: dict[str, str] | None = None,
    ) -> None:
        """Validate the target widget type for an interaction.

        Provides helpful error messages when the wrong interaction
        method is used (e.g. click on a checkbox).

        Args:
            selector: Widget selector.
            action: The interaction being attempted.
            allowed_types: Widget types that support this action.
            suggestions: Map of wrong-type to suggested action name.
        """
        if self._tree is None:
            return
        node = _find_node_by_selector(self._tree, selector)
        if node is None:
            return  # will fail later with ElementNotFoundError
        widget_type = node.get("type", "")
        if not allowed_types or widget_type in allowed_types:
            return
        if suggestions and widget_type in suggestions:
            suggested = suggestions[widget_type]
            raise TypeError(
                f"cannot {action} a {widget_type} widget -- use {suggested}() instead"
            )
        # Not in allowed set but no specific suggestion
        if allowed_types:
            raise TypeError(
                f"cannot {action} a {widget_type} widget "
                f"(expected one of: {', '.join(sorted(allowed_types))})"
            )

    def _read_toggle_value(self, selector: str) -> bool:
        """Read the current toggle/check state from the local tree."""
        if self._tree is None:
            return False
        node = _find_node_by_selector(self._tree, selector)
        if node is None:
            return False
        props = node.get("props", {})
        # checkbox uses "checked", toggler uses "is_toggled"
        return bool(props.get("checked", props.get("is_toggled", False)))


def _available_ids(tree: Node | None) -> list[str]:
    """Collect available IDs from the tree for error messages."""
    if tree is None:
        return []
    from plushie.tree import ids

    return ids(tree)


__all__ = [
    "AppFixture",
]
