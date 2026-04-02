"""Tests for plushie.effects."""

from __future__ import annotations

from plushie import effects
from plushie.effects import _reset_counter


class TestWireIdGeneration:
    def setup_method(self) -> None:
        _reset_counter()

    def test_ids_are_monotonic(self) -> None:
        a = effects.file_open("a")
        b = effects.file_open("b")
        id_a = a.payload["id"]
        id_b = b.payload["id"]
        assert id_a.startswith("ef_")
        assert id_b.startswith("ef_")
        num_a = int(id_a.split("_")[1])
        num_b = int(id_b.split("_")[1])
        assert num_b > num_a

    def test_ids_are_unique(self) -> None:
        ids = {effects.clipboard_read(f"t{i}").payload["id"] for i in range(100)}
        assert len(ids) == 100


class TestTagInPayload:
    def setup_method(self) -> None:
        _reset_counter()

    def test_tag_stored_in_payload(self) -> None:
        cmd = effects.file_open("import", title="Open")
        assert cmd.payload["tag"] == "import"

    def test_different_tags(self) -> None:
        a = effects.file_open("a")
        b = effects.file_open("b")
        assert a.payload["tag"] == "a"
        assert b.payload["tag"] == "b"


class TestFileDialogs:
    def setup_method(self) -> None:
        _reset_counter()

    def test_file_open(self) -> None:
        cmd = effects.file_open("open", title="Open")
        assert cmd.type == "effect"
        assert cmd.payload["kind"] == "file_open"
        assert cmd.payload["opts"]["title"] == "Open"
        assert "id" in cmd.payload

    def test_file_open_no_opts(self) -> None:
        cmd = effects.file_open("open")
        assert cmd.payload["opts"] == {}

    def test_file_open_with_filters(self) -> None:
        cmd = effects.file_open("open", filters=[("Images", "*.png")])
        assert cmd.payload["opts"]["filters"] == [("Images", "*.png")]

    def test_file_open_multiple(self) -> None:
        cmd = effects.file_open_multiple("multi", title="Select")
        assert cmd.payload["kind"] == "file_open_multiple"
        assert cmd.payload["opts"]["title"] == "Select"

    def test_file_save(self) -> None:
        cmd = effects.file_save("save", default_name="doc.txt")
        assert cmd.payload["kind"] == "file_save"
        assert cmd.payload["opts"]["default_name"] == "doc.txt"

    def test_directory_select(self) -> None:
        cmd = effects.directory_select("dir", title="Pick folder")
        assert cmd.payload["kind"] == "directory_select"

    def test_directory_select_multiple(self) -> None:
        cmd = effects.directory_select_multiple("dirs")
        assert cmd.payload["kind"] == "directory_select_multiple"


class TestClipboard:
    def setup_method(self) -> None:
        _reset_counter()

    def test_clipboard_read(self) -> None:
        cmd = effects.clipboard_read("clip")
        assert cmd.payload["kind"] == "clipboard_read"

    def test_clipboard_write(self) -> None:
        cmd = effects.clipboard_write("clip", "hello")
        assert cmd.payload["kind"] == "clipboard_write"
        assert cmd.payload["opts"]["text"] == "hello"

    def test_clipboard_read_html(self) -> None:
        cmd = effects.clipboard_read_html("clip")
        assert cmd.payload["kind"] == "clipboard_read_html"

    def test_clipboard_write_html(self) -> None:
        cmd = effects.clipboard_write_html("clip", "<b>hi</b>", alt_text="hi")
        assert cmd.payload["kind"] == "clipboard_write_html"
        assert cmd.payload["opts"]["html"] == "<b>hi</b>"
        assert cmd.payload["opts"]["alt_text"] == "hi"

    def test_clipboard_write_html_no_alt(self) -> None:
        cmd = effects.clipboard_write_html("clip", "<b>hi</b>")
        assert "alt_text" not in cmd.payload["opts"]

    def test_clipboard_clear(self) -> None:
        cmd = effects.clipboard_clear("clip")
        assert cmd.payload["kind"] == "clipboard_clear"

    def test_clipboard_read_primary(self) -> None:
        cmd = effects.clipboard_read_primary("clip")
        assert cmd.payload["kind"] == "clipboard_read_primary"

    def test_clipboard_write_primary(self) -> None:
        cmd = effects.clipboard_write_primary("clip", "text")
        assert cmd.payload["kind"] == "clipboard_write_primary"
        assert cmd.payload["opts"]["text"] == "text"


class TestNotification:
    def setup_method(self) -> None:
        _reset_counter()

    def test_basic(self) -> None:
        cmd = effects.notification("notify", "Title", "Body")
        assert cmd.payload["kind"] == "notification"
        assert cmd.payload["opts"]["title"] == "Title"
        assert cmd.payload["opts"]["body"] == "Body"

    def test_with_all_options(self) -> None:
        cmd = effects.notification(
            "alert",
            "Alert",
            "Something happened",
            icon="warning",
            timeout=5000,
            urgency="critical",
            sound="default",
        )
        opts = cmd.payload["opts"]
        assert opts["icon"] == "warning"
        assert opts["timeout"] == 5000
        assert opts["urgency"] == "critical"
        assert opts["sound"] == "default"

    def test_none_options_excluded(self) -> None:
        cmd = effects.notification("notify", "T", "B")
        opts = cmd.payload["opts"]
        assert "icon" not in opts
        assert "timeout" not in opts
        assert "urgency" not in opts
        assert "sound" not in opts


class TestDefaultTimeout:
    def test_file_dialog_timeout(self) -> None:
        assert effects.default_timeout("file_open") == 120_000

    def test_clipboard_timeout(self) -> None:
        assert effects.default_timeout("clipboard_read") == 5_000

    def test_notification_timeout(self) -> None:
        assert effects.default_timeout("notification") == 5_000

    def test_unknown_kind(self) -> None:
        assert effects.default_timeout("unknown") is None


class TestGenericRequest:
    def setup_method(self) -> None:
        _reset_counter()

    def test_generic_request(self) -> None:
        cmd = effects.request("clip", "clipboard_read")
        assert cmd.type == "effect"
        assert cmd.payload["kind"] == "clipboard_read"
        assert cmd.payload["tag"] == "clip"
        assert "id" in cmd.payload
