"""Tests for code blocks in docs/effects.md.

Verifies that effect function calls return correct Command types
with the expected payload structure.
"""

from __future__ import annotations

from plushie import effects
from plushie.commands import Command

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def setup_function() -> None:
    """Reset the effect ID counter before each test for deterministic IDs."""
    effects._reset_counter()


# ---------------------------------------------------------------------------
# test_file_dialogs
# ---------------------------------------------------------------------------


def test_file_open():
    """effects.file_open() returns a Command with the right payload."""
    cmd = effects.file_open(
        "open",
        title="Choose a file",
        filters=[("Text files", "*.txt"), ("All files", "*")],
    )

    assert isinstance(cmd, Command)
    assert cmd.type == "effect"
    assert cmd.payload["kind"] == "file_open"
    assert cmd.payload["opts"]["title"] == "Choose a file"
    assert len(cmd.payload["opts"]["filters"]) == 2


def test_file_open_with_directory():
    """effects.file_open() accepts a starting directory."""
    cmd = effects.file_open(
        "open",
        title="Open Project",
        directory="/home/user/projects",
        filters=[("Python", "*.py"), ("All files", "*")],
    )

    assert cmd.payload["opts"]["directory"] == "/home/user/projects"


def test_file_open_multiple():
    """effects.file_open_multiple() opens a multi-file dialog."""
    cmd = effects.file_open_multiple(
        "multi",
        title="Select images",
        filters=[("Images", "*.png"), ("JPEG", "*.jpg")],
    )

    assert cmd.payload["kind"] == "file_open_multiple"
    assert len(cmd.payload["opts"]["filters"]) == 2


def test_file_save():
    """effects.file_save() opens a save dialog."""
    cmd = effects.file_save(
        "save",
        title="Save As",
        default_name="untitled.txt",
        filters=[("Text files", "*.txt")],
    )

    assert cmd.payload["kind"] == "file_save"
    assert cmd.payload["opts"]["default_name"] == "untitled.txt"


def test_directory_select():
    """effects.directory_select("dir", ) opens a directory picker."""
    cmd = effects.directory_select("dir", title="Choose output directory")

    assert cmd.payload["kind"] == "directory_select"
    assert cmd.payload["opts"]["title"] == "Choose output directory"


def test_directory_select_multiple():
    """effects.directory_select_multiple("dirs", ) opens a multi-directory picker."""
    cmd = effects.directory_select_multiple("dirs", title="Select folders")

    assert cmd.payload["kind"] == "directory_select_multiple"


# ---------------------------------------------------------------------------
# test_clipboard
# ---------------------------------------------------------------------------


def test_clipboard_read():
    """effects.clipboard_read("clip") reads the clipboard."""
    cmd = effects.clipboard_read("clip")

    assert cmd.payload["kind"] == "clipboard_read"


def test_clipboard_write():
    """effects.clipboard_write("clip", ) writes text to the clipboard."""
    cmd = effects.clipboard_write("clip", "Hello, clipboard")

    assert cmd.payload["kind"] == "clipboard_write"
    assert cmd.payload["opts"]["text"] == "Hello, clipboard"


def test_clipboard_read_html():
    """effects.clipboard_read_html("clip") reads HTML from the clipboard."""
    cmd = effects.clipboard_read_html("clip")

    assert cmd.payload["kind"] == "clipboard_read_html"


def test_clipboard_write_html():
    """effects.clipboard_write_html("clip", ) writes HTML to the clipboard."""
    cmd = effects.clipboard_write_html("clip", "<b>Bold</b>", alt_text="Bold")

    assert cmd.payload["kind"] == "clipboard_write_html"
    assert cmd.payload["opts"]["html"] == "<b>Bold</b>"
    assert cmd.payload["opts"]["alt_text"] == "Bold"


def test_clipboard_clear():
    """effects.clipboard_clear("clip") clears the clipboard."""
    cmd = effects.clipboard_clear("clip")

    assert cmd.payload["kind"] == "clipboard_clear"


def test_clipboard_read_primary():
    """effects.clipboard_read_primary("clip") reads primary selection (Linux)."""
    cmd = effects.clipboard_read_primary("clip")

    assert cmd.payload["kind"] == "clipboard_read_primary"


def test_clipboard_write_primary():
    """effects.clipboard_write_primary("clip", ) writes to primary selection."""
    cmd = effects.clipboard_write_primary("clip", "Selected text")

    assert cmd.payload["kind"] == "clipboard_write_primary"
    assert cmd.payload["opts"]["text"] == "Selected text"


# ---------------------------------------------------------------------------
# test_notifications
# ---------------------------------------------------------------------------


def test_notification():
    """effects.notification() shows an OS notification."""
    cmd = effects.notification(
        "notify",
        "Build Complete",
        "Your project compiled successfully.",
        icon="dialog-information",
        timeout=5000,
        urgency="normal",
        sound="complete",
    )

    assert cmd.payload["kind"] == "notification"
    opts = cmd.payload["opts"]
    assert opts["title"] == "Build Complete"
    assert opts["body"] == "Your project compiled successfully."
    assert opts["icon"] == "dialog-information"
    assert opts["timeout"] == 5000
    assert opts["urgency"] == "normal"
    assert opts["sound"] == "complete"


# ---------------------------------------------------------------------------
# test_raw_request
# ---------------------------------------------------------------------------


def test_raw_request():
    """effects.request() sends a generic effect with arbitrary payload."""
    cmd = effects.request("custom", "some_new_effect", foo="bar", baz=42)

    assert cmd.type == "effect"
    assert cmd.payload["tag"] == "custom"
    assert cmd.payload["kind"] == "some_new_effect"
    assert cmd.payload["opts"]["foo"] == "bar"
    assert cmd.payload["opts"]["baz"] == 42


# ---------------------------------------------------------------------------
# test_effect_id_generation
# ---------------------------------------------------------------------------


def test_effect_id_auto_generated():
    """Each effect call gets a unique, monotonically increasing ID."""
    cmd1 = effects.clipboard_read("clip")
    cmd2 = effects.clipboard_read("clip")

    id1 = cmd1.payload["id"]
    id2 = cmd2.payload["id"]
    assert id1 != id2
    assert id1.startswith("ef_")
    assert id2.startswith("ef_")


def test_effect_tag_in_payload():
    """The effect tag is stored in the command payload."""
    cmd = effects.file_open("import", title="Pick a file")
    assert cmd.payload["tag"] == "import"
    assert cmd.payload["id"].startswith("ef_")


# ---------------------------------------------------------------------------
# test_all_effects_return_commands
# ---------------------------------------------------------------------------


def test_all_effects_return_command_type():
    """Every effect function returns a Command instance."""
    all_cmds = [
        effects.file_open(
            "open",
        ),
        effects.file_open_multiple(
            "multi",
        ),
        effects.file_save(
            "save",
        ),
        effects.directory_select(
            "dir",
        ),
        effects.directory_select_multiple(
            "dirs",
        ),
        effects.clipboard_read("clip"),
        effects.clipboard_write("clip", "test"),
        effects.clipboard_read_html("clip"),
        effects.clipboard_write_html("clip", "<b>test</b>"),
        effects.clipboard_clear("clip"),
        effects.clipboard_read_primary("clip"),
        effects.clipboard_write_primary("clip", "test"),
        effects.notification("notify", "Title", "Body"),
        effects.request("custom", "custom_effect"),
    ]

    for cmd in all_cmds:
        assert isinstance(cmd, Command), f"Expected Command, got {type(cmd)}"
        assert cmd.type == "effect"
