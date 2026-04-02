"""Subscription types for ongoing event sources.

Return subscriptions from the ``subscribe`` callback.  The runtime diffs
the list each cycle using ``key``: subscriptions with the same key are
considered identical and kept alive; new keys trigger a subscribe message
to the renderer; removed keys trigger an unsubscribe.

Renderer subscriptions accept an optional ``max_rate`` that tells the
renderer to coalesce events beyond the given rate (events per second).

Usage::

    from plushie.subscriptions import Subscription

    def subscribe(self, model):
        subs = [Subscription.on_key_press("keys")]
        if model.animating:
            subs.append(Subscription.every(16, "tick"))
        return subs

Window-scoped subscriptions only receive events from a specific
window::

    Subscription.on_key_press("editor_keys", window="editor")

    Subscription.for_window("editor", [
        Subscription.on_key_press("editor_keys"),
        Subscription.on_pointer_move("editor_mouse", max_rate=60),
    ])
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class Subscription:
    """A subscription spec describing an ongoing event source.

    Subscriptions are pure data.  The runtime interprets them to manage
    subscribe/unsubscribe messages to the renderer and local timers.

    Attributes:
        kind: The subscription kind (e.g. ``"every"``,
            ``"on_key_press"``).
        tag: Identifier for subscription management and diffing.
        interval_ms: Timer interval in milliseconds (``every`` only).
        max_rate: Optional rate limit (events per second) for renderer
            subscriptions.  ``None`` means no limit.
        window_id: Optional window scope.  When set, the renderer only
            delivers events from the specified window.  ``None`` means
            events from all windows (default).
    """

    kind: str
    tag: str
    interval_ms: int | None = None
    max_rate: int | None = None
    window_id: str | None = None

    @property
    def key(self) -> tuple[str, ...]:
        """Unique identity for subscription diffing.

        Timer subscriptions key on ``(kind, interval_ms, tag)``.
        Renderer subscriptions key on ``(kind, tag)`` or
        ``(kind, tag, window_id)`` when window-scoped.
        """
        if self.kind == "every":
            return ("every", str(self.interval_ms), self.tag)
        if self.window_id is not None:
            return (self.kind, self.tag, self.window_id)
        return (self.kind, self.tag)

    @property
    def wire_kind(self) -> str:
        """Wire format kind string for this subscription."""
        return self.kind

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    @staticmethod
    def every(interval_ms: int, tag: str) -> Subscription:
        """Timer that fires every *interval_ms* milliseconds.

        Delivers a ``TimerTick`` event with the given *tag* to ``update``.
        """
        return Subscription(kind="every", tag=tag, interval_ms=interval_ms)

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    @staticmethod
    def on_key_press(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to key press events."""
        return Subscription(
            kind="on_key_press", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_key_release(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to key release events."""
        return Subscription(
            kind="on_key_release", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_modifiers_changed(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to keyboard modifier state changes (shift, ctrl, alt, etc.)."""
        return Subscription(
            kind="on_modifiers_changed", tag=tag, max_rate=max_rate, window_id=window
        )

    # ------------------------------------------------------------------
    # Pointer (mouse, touch, pen)
    # ------------------------------------------------------------------

    @staticmethod
    def on_pointer_move(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to pointer movement events (also delivers enter/leave).

        Delivers ``Move``, ``Enter``, and ``Exit`` events with
        ``id=window_id`` and ``scope=()``.
        """
        return Subscription(
            kind="on_pointer_move", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_pointer_button(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to pointer button press and release events.

        Delivers ``Press`` and ``Release`` events with ``id=window_id``
        and ``scope=()``.
        """
        return Subscription(
            kind="on_pointer_button", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_pointer_scroll(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to pointer scroll (wheel) events.

        Delivers ``Scroll`` events with ``id=window_id`` and ``scope=()``.
        """
        return Subscription(
            kind="on_pointer_scroll", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_pointer_touch(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to touch pointer events.

        Delivers ``Press``, ``Move``, and ``Release`` events with
        ``pointer="touch"`` and ``id=window_id``.
        """
        return Subscription(
            kind="on_touch", tag=tag, max_rate=max_rate, window_id=window
        )

    # ------------------------------------------------------------------
    # IME
    # ------------------------------------------------------------------

    @staticmethod
    def on_ime(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to IME (Input Method Editor) events."""
        return Subscription(kind="on_ime", tag=tag, max_rate=max_rate, window_id=window)

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------

    @staticmethod
    def on_window_event(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to all window events (resize, move, focus, etc.)."""
        return Subscription(
            kind="on_window_event", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_window_open(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to window open events."""
        return Subscription(
            kind="on_window_open", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_window_close(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to window close request events."""
        return Subscription(
            kind="on_window_close", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_window_resize(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to window resize events."""
        return Subscription(
            kind="on_window_resize", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_window_move(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to window move events."""
        return Subscription(
            kind="on_window_move", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_window_focus(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to window focus gained events."""
        return Subscription(
            kind="on_window_focus", tag=tag, max_rate=max_rate, window_id=window
        )

    @staticmethod
    def on_window_unfocus(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to window focus lost events."""
        return Subscription(
            kind="on_window_unfocus", tag=tag, max_rate=max_rate, window_id=window
        )

    # ------------------------------------------------------------------
    # File drop
    # ------------------------------------------------------------------

    @staticmethod
    def on_file_drop(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to file drop events (also delivers hovered/hover-left)."""
        return Subscription(
            kind="on_file_drop", tag=tag, max_rate=max_rate, window_id=window
        )

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    @staticmethod
    def on_animation_frame(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to animation frame events (vsync ticks)."""
        return Subscription(
            kind="on_animation_frame", tag=tag, max_rate=max_rate, window_id=window
        )

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    @staticmethod
    def on_theme_change(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to system theme changes (light/dark mode)."""
        return Subscription(
            kind="on_theme_change", tag=tag, max_rate=max_rate, window_id=window
        )

    # ------------------------------------------------------------------
    # Catch-all
    # ------------------------------------------------------------------

    @staticmethod
    def on_event(
        tag: str, *, max_rate: int | None = None, window: str | None = None
    ) -> Subscription:
        """Subscribe to all renderer events (catch-all)."""
        return Subscription(
            kind="on_event", tag=tag, max_rate=max_rate, window_id=window
        )

    # ------------------------------------------------------------------
    # Window scoping
    # ------------------------------------------------------------------

    @staticmethod
    def for_window(
        window_id: str, subscriptions: list[Subscription]
    ) -> list[Subscription]:
        """Scope a list of subscriptions to a specific window.

        Window-scoped subscriptions tell the renderer to only deliver
        events from the given window.  Without a window scope,
        subscriptions receive events from all windows.

        Example::

            Subscription.for_window("editor", [
                Subscription.on_key_press("editor_keys"),
                Subscription.on_pointer_move("editor_mouse", max_rate=60),
            ])
        """
        return [replace(sub, window_id=window_id) for sub in subscriptions]

    # ------------------------------------------------------------------
    # Tag transformation
    # ------------------------------------------------------------------

    def map_tag(self, mapper: Callable[[Any], Any]) -> Subscription:
        """Return a new subscription with a transformed tag.

        Used by the runtime to namespace canvas widget subscription tags
        so timer events can be routed back to the correct widget.

        Args:
            mapper: Function that transforms the tag value.
        """
        return replace(self, tag=mapper(self.tag))


__all__ = ["Subscription"]
