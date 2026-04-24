"""Tests mirroring code examples from docs/running.md.

Validates settings/rate-limiting patterns, IoStreamAdapter construction,
and framing encode/decode usage.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from plushie import ui
from plushie.app import App
from plushie.framing import JsonFraming, MsgpackFraming
from plushie.subscriptions import Subscription
from plushie.transport import IoStreamAdapter

RUNNING_DOC = Path(__file__).parents[2] / "docs" / "running.md"


def test_running_doc_does_not_use_transport_kwarg_for_run() -> None:
    """The stdio mode example should use connect, not a run() transport kwarg."""
    text = RUNNING_DOC.read_text()

    assert 'transport="stdio"' not in text
    assert "plushie.run(MyApp, daemon=True)" in text
    assert "python -m plushie connect my_app:MyApp" in text


# ---------------------------------------------------------------------------
# Settings / rate limiting
# ---------------------------------------------------------------------------


class SettingsApp(App[dict[str, Any]]):
    """App with settings() returning a default_event_rate."""

    def init(self) -> dict[str, Any]:
        return {}

    def update(self, model: dict[str, Any], event: object) -> dict[str, Any]:
        return model

    def view(self, model: dict[str, Any]) -> dict[str, Any]:
        return ui.window("main")

    def settings(self) -> dict[str, Any]:
        return {"default_event_rate": 60}


class DashboardApp(App[dict[str, Any]]):
    """Dashboard app with lower event rate."""

    def init(self) -> dict[str, Any]:
        return {}

    def update(self, model: dict[str, Any], event: object) -> dict[str, Any]:
        return model

    def view(self, model: dict[str, Any]) -> dict[str, Any]:
        return ui.window("main")

    def settings(self) -> dict[str, Any]:
        return {"default_event_rate": 15}


class TestSettingsRateLimiting:
    """Doc section: Event rate limiting: Global default."""

    def test_settings_returns_event_rate(self) -> None:
        app = SettingsApp()
        settings = app.settings()
        assert settings["default_event_rate"] == 60

    def test_dashboard_lower_rate(self) -> None:
        app = DashboardApp()
        settings = app.settings()
        assert settings["default_event_rate"] == 15


# ---------------------------------------------------------------------------
# Per-subscription rate limiting
# ---------------------------------------------------------------------------


class TestPerSubscriptionRate:
    """Doc section: Event rate limiting: Per-subscription."""

    def test_mouse_move_rate(self) -> None:
        sub = Subscription.on_pointer_move(max_rate=30)
        assert sub.kind == "on_pointer_move"
        assert sub.max_rate == 30

    def test_animation_frame_rate(self) -> None:
        sub = Subscription.on_animation_frame(max_rate=60)
        assert sub.kind == "on_animation_frame"
        assert sub.max_rate == 60

    def test_capture_only_zero_rate(self) -> None:
        sub = Subscription.on_pointer_move(max_rate=0)
        assert sub.max_rate == 0


# ---------------------------------------------------------------------------
# Per-widget rate limiting
# ---------------------------------------------------------------------------


class TestPerWidgetRate:
    """Doc section: Event rate limiting: Per-widget."""

    def test_slider_event_rate(self) -> None:
        node = ui.slider("volume", (0, 100), 50, event_rate=15)
        assert node["props"]["event_rate"] == 15

    def test_slider_different_rates(self) -> None:
        slow = ui.slider("volume", (0, 100), 50, event_rate=15)
        fast = ui.slider("seek", (0, 300), 100, event_rate=60)
        assert slow["props"]["event_rate"] == 15
        assert fast["props"]["event_rate"] == 60


# ---------------------------------------------------------------------------
# IoStreamAdapter construction
# ---------------------------------------------------------------------------


class TestIoStreamAdapter:
    """Doc section: IoStreamAdapter construction from byte streams."""

    def test_adapter_accepts_file_like_objects(self) -> None:
        """Verify IoStreamAdapter can be constructed with io.BytesIO objects."""
        reader = io.BytesIO(b"")
        writer = io.BytesIO()

        # The adapter starts a reader thread immediately, but with an
        # empty stream it will just hit EOF and stop. We verify it
        # constructs without error.
        adapter = IoStreamAdapter(reader, writer)  # type: ignore[arg-type]
        assert adapter is not None


# ---------------------------------------------------------------------------
# Framing encode/decode
# ---------------------------------------------------------------------------


class TestMsgpackFraming:
    """Doc section: Framing: MsgpackFraming encode + feed round-trip."""

    def test_encode_decode_round_trip(self) -> None:
        msg = {"type": "snapshot", "tree": {"id": "root"}}
        encoded = MsgpackFraming.encode(msg)

        framing = MsgpackFraming()
        messages = framing.feed(encoded)

        assert len(messages) == 1
        assert messages[0]["type"] == "snapshot"

    def test_partial_feed_buffers(self) -> None:
        msg = {"hello": "world"}
        encoded = MsgpackFraming.encode(msg)

        framing = MsgpackFraming()
        # Feed first half; should return nothing
        half = len(encoded) // 2
        messages = framing.feed(encoded[:half])
        assert messages == []

        # Feed the rest; now should decode
        messages = framing.feed(encoded[half:])
        assert len(messages) == 1
        assert messages[0]["hello"] == "world"


class TestJsonFraming:
    """Doc section: Framing: JsonFraming encode + feed round-trip."""

    def test_encode_decode_round_trip(self) -> None:
        msg = {"type": "settings", "theme": "dark"}
        encoded = JsonFraming.encode(msg)

        framing = JsonFraming()
        messages = framing.feed(encoded)

        assert len(messages) == 1
        assert messages[0]["type"] == "settings"
        assert messages[0]["theme"] == "dark"

    def test_multiple_messages(self) -> None:
        msg1 = {"a": 1}
        msg2 = {"b": 2}
        data = JsonFraming.encode(msg1) + JsonFraming.encode(msg2)

        framing = JsonFraming()
        messages = framing.feed(data)

        assert len(messages) == 2
        assert messages[0]["a"] == 1
        assert messages[1]["b"] == 2
