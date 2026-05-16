"""Tests for the renderer subprocess environment whitelist.

The whitelist must match the canonical list shared across every host
SDK: secrets and unrelated vars never propagate to the renderer child,
while display/rendering/locale/accessibility/font/plushie-toggle vars
do.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from plushie.connection import _build_env


def test_forwards_whitelisted_exact_vars(monkeypatch):
    monkeypatch.setenv("HOME", "/home/tester")
    monkeypatch.setenv("RUST_LOG", "plushie=debug")

    env = _build_env()

    assert env.get("HOME") == "/home/tester"
    assert env.get("RUST_LOG") == "plushie=debug"


def test_forwards_display_server_vars(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setenv("WAYLAND_SOCKET", "/run/user/1000/wayland-0")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setenv("XDG_DATA_DIRS", "/usr/share")
    monkeypatch.setenv("XDG_DATA_HOME", "/home/tester/.local/share")

    env = _build_env()

    assert env.get("WAYLAND_DISPLAY") == "wayland-1"
    assert env.get("WAYLAND_SOCKET") == "/run/user/1000/wayland-0"
    assert env.get("XDG_RUNTIME_DIR") == "/run/user/1000"
    assert env.get("XDG_DATA_DIRS") == "/usr/share"
    assert env.get("XDG_DATA_HOME") == "/home/tester/.local/share"


def test_strips_non_canonical_desktop_vars(monkeypatch):
    """Vars not in the canonical list must be dropped even if desktop-related."""
    for key, value in {
        "XDG_CURRENT_DESKTOP": "sway",
        "XDG_SESSION_TYPE": "wayland",
        "GDK_BACKEND": "wayland",
        "GSK_RENDERER": "ngl",
        "CLUTTER_BACKEND": "wayland",
        "SDL_VIDEO_wayland": "1",
        "QT_QPA_PLATFORM": "wayland",
        "SWAYSOCK": "/run/user/1000/sway-ipc.sock",
    }.items():
        monkeypatch.setenv(key, value)

    env = _build_env()

    for key in (
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_TYPE",
        "GDK_BACKEND",
        "GSK_RENDERER",
        "CLUTTER_BACKEND",
        "SDL_VIDEO_wayland",
        "QT_QPA_PLATFORM",
        "SWAYSOCK",
    ):
        assert key not in env, f"{key} must not be forwarded to the renderer"


def test_forwards_prefix_matched_vars(monkeypatch):
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("MESA_GL_VERSION_OVERRIDE", "4.5")

    env = _build_env()

    assert env.get("LC_ALL") == "en_US.UTF-8"
    assert env.get("MESA_GL_VERSION_OVERRIDE") == "4.5"


def test_forwards_plushie_no_catch_unwind(monkeypatch):
    monkeypatch.setenv("PLUSHIE_NO_CATCH_UNWIND", "1")

    env = _build_env()

    assert env.get("PLUSHIE_NO_CATCH_UNWIND") == "1"


def test_plushie_closed_allowlist(monkeypatch):
    """Only PLUSHIE_NO_CATCH_UNWIND crosses the process boundary.

    All other PLUSHIE_* names are host-side, launcher-set, or secrets that
    must not leak to the renderer subprocess.
    """
    monkeypatch.setenv("PLUSHIE_NO_CATCH_UNWIND", "1")
    for name in (
        "PLUSHIE_TOKEN",
        "PLUSHIE_SOCKET",
        "PLUSHIE_TRANSPORT",
        "PLUSHIE_FORMAT",
        "PLUSHIE_RUST_SOURCE_PATH",
        "PLUSHIE_BINARY_PATH",
        "PLUSHIE_PACKAGE_DIR",
        "PLUSHIE_PACKAGE_READY_FILE",
        "PLUSHIE_RELEASE_BASE_URL",
        "PLUSHIE_CACHE_DIR",
    ):
        monkeypatch.setenv(name, "should-not-leak")

    env = _build_env()

    assert env.get("PLUSHIE_NO_CATCH_UNWIND") == "1"
    for name in (
        "PLUSHIE_TOKEN",
        "PLUSHIE_SOCKET",
        "PLUSHIE_TRANSPORT",
        "PLUSHIE_FORMAT",
        "PLUSHIE_RUST_SOURCE_PATH",
        "PLUSHIE_BINARY_PATH",
        "PLUSHIE_PACKAGE_DIR",
        "PLUSHIE_PACKAGE_READY_FILE",
        "PLUSHIE_RELEASE_BASE_URL",
        "PLUSHIE_CACHE_DIR",
    ):
        assert name not in env, f"{name} must not be forwarded to the renderer"


def test_strips_non_whitelisted_secrets(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "leak-me")
    monkeypatch.setenv("GITHUB_TOKEN", "also-leak")
    monkeypatch.setenv("DATABASE_URL", "postgres://secret")

    env = _build_env()

    assert "AWS_ACCESS_KEY_ID" not in env
    assert "GITHUB_TOKEN" not in env
    assert "DATABASE_URL" not in env


def test_extra_overrides_take_precedence():
    env = _build_env({"RUST_LOG": "plushie=trace", "CUSTOM_VAR": "hi"})

    assert env.get("RUST_LOG") == "plushie=trace"
    assert env.get("CUSTOM_VAR") == "hi"


def test_extra_values_are_converted_to_strings():
    env = _build_env({"PLUSHIE_PORT": 1234, "PLUSHIE_ENABLED": True})

    assert env.get("PLUSHIE_PORT") == "1234"
    assert env.get("PLUSHIE_ENABLED") == "True"


def test_forwarded_environment_values_are_converted_to_strings():
    with patch("plushie.connection.os.environ", {"HOME": 1234}):
        env = _build_env()

    assert env.get("HOME") == "1234"


def test_forwards_windows_critical_vars(monkeypatch):
    """Windows DLL loader, PATHEXT resolution, and tempdir vars are forwarded.

    Harmless on non-Windows hosts: they simply won't be present in the env.
    """
    monkeypatch.setenv("SystemRoot", "C:\\Windows")
    monkeypatch.setenv("WINDIR", "C:\\Windows")
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT")
    monkeypatch.setenv("TEMP", "C:\\Temp")
    monkeypatch.setenv("TMP", "C:\\Temp")

    env = _build_env()

    assert env.get("SystemRoot") == "C:\\Windows"
    assert env.get("WINDIR") == "C:\\Windows"
    assert env.get("PATHEXT") == ".COM;.EXE;.BAT"
    assert env.get("TEMP") == "C:\\Temp"
    assert env.get("TMP") == "C:\\Temp"


def test_subprocess_does_not_see_leaked_secret(monkeypatch):
    """The filtered env dict must be usable with subprocess.Popen."""
    monkeypatch.setenv("SHOULD_NOT_LEAK", "xxx")

    env = _build_env()

    assert "SHOULD_NOT_LEAK" not in env
    # Sanity: the current process does still see it.
    assert os.environ.get("SHOULD_NOT_LEAK") == "xxx"
