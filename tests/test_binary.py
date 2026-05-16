"""Tests for binary resolution, download, and build helpers."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from plushie.binary import (
    ChecksumError,
    _verify_checksum,
    build_wasm,
    check_rust_version,
    detect_arch,
    detect_os,
    download,
    download_name,
    download_tool,
    download_wasm,
    launcher_name,
    release_name,
    sync_renderer_with_tool,
    tool_name,
    tool_release_name,
)


def write_checksum(path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".sha256").write_text(
        f"{digest}  {path.name}\n",
        encoding="utf-8",
    )


# -- Platform detection ------------------------------------------------------


class TestDetectOs:
    def test_linux(self) -> None:
        with patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "linux"
            assert detect_os() == "linux"

    def test_darwin(self) -> None:
        with patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert detect_os() == "darwin"

    def test_windows(self) -> None:
        with patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "win32"
            assert detect_os() == "windows"

    def test_unsupported(self) -> None:
        with patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "haiku"
            with pytest.raises(RuntimeError, match="unsupported platform"):
                detect_os()


class TestDetectArch:
    def test_x86_64(self) -> None:
        with patch("plushie.binary.platform") as mock_plat:
            mock_plat.machine.return_value = "x86_64"
            assert detect_arch() == "x86_64"

    def test_aarch64(self) -> None:
        with patch("plushie.binary.platform") as mock_plat:
            mock_plat.machine.return_value = "aarch64"
            assert detect_arch() == "aarch64"

    def test_unsupported(self) -> None:
        with patch("plushie.binary.platform") as mock_plat:
            mock_plat.machine.return_value = "mips"
            with pytest.raises(RuntimeError, match="unsupported architecture"):
                detect_arch()


class TestDownloadName:
    def test_linux_x86(self) -> None:
        assert download_name(os_name="linux") == "plushie-renderer"

    def test_windows_gets_exe(self) -> None:
        name = download_name(os_name="windows")
        assert name.endswith(".exe")


class TestToolName:
    def test_linux_x86(self) -> None:
        assert tool_name(os_name="linux") == "plushie"

    def test_windows_gets_exe(self) -> None:
        name = tool_name(os_name="windows")
        assert name.endswith(".exe")


class TestReleaseName:
    def test_linux_x86(self) -> None:
        assert (
            release_name(os_name="linux", arch="x86_64")
            == "plushie-renderer-linux-x86_64"
        )


class TestToolReleaseName:
    def test_linux_x86(self) -> None:
        assert (
            tool_release_name(os_name="linux", arch="x86_64") == "plushie-linux-x86_64"
        )


# -- Checksum verification --------------------------------------------------


class TestVerifyChecksum:
    def test_valid_checksum(self, tmp_path: Path) -> None:
        content = b"hello plushie"
        file_path = tmp_path / "artifact"
        file_path.write_bytes(content)
        expected_hash = hashlib.sha256(content).hexdigest()

        checksum_body = f"{expected_hash}  artifact\n".encode()

        with patch("plushie.binary.urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = checksum_body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            _verify_checksum(file_path, "https://example.com/artifact.sha256")

        assert file_path.exists()

    def test_mismatched_checksum_deletes_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "artifact"
        file_path.write_bytes(b"real content")

        checksum_body = b"0000000000000000000000000000000000000000000000000000000000000000  artifact\n"

        with patch("plushie.binary.urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = checksum_body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp

            with pytest.raises(ChecksumError, match="Checksum mismatch"):
                _verify_checksum(file_path, "https://example.com/artifact.sha256")

        assert not file_path.exists()

    def test_unavailable_checksum_deletes_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "artifact"
        file_path.write_bytes(b"content")

        with patch("plushie.binary.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = OSError("network down")

            with pytest.raises(ChecksumError, match="could not be downloaded"):
                _verify_checksum(file_path, "https://example.com/artifact.sha256")

        assert not file_path.exists()


# -- Rust version check -----------------------------------------------------


class TestCheckRustVersion:
    def test_sufficient_version(self) -> None:
        result = subprocess.CompletedProcess(
            args=["rustc", "--version"],
            returncode=0,
            stdout="rustc 1.92.0 (abcdef123 2025-01-01)",
            stderr="",
        )
        with patch("plushie.binary.subprocess.run", return_value=result):
            check_rust_version()

    def test_newer_version(self) -> None:
        result = subprocess.CompletedProcess(
            args=["rustc", "--version"],
            returncode=0,
            stdout="rustc 1.93.1 (abcdef123 2025-03-01)",
            stderr="",
        )
        with patch("plushie.binary.subprocess.run", return_value=result):
            check_rust_version()

    def test_old_version_raises(self) -> None:
        result = subprocess.CompletedProcess(
            args=["rustc", "--version"],
            returncode=0,
            stdout="rustc 1.80.0 (abcdef123 2024-06-01)",
            stderr="",
        )
        with (
            patch("plushie.binary.subprocess.run", return_value=result),
            pytest.raises(RuntimeError, match=r"requires >= 1\.92\.0"),
        ):
            check_rust_version()

    def test_rustc_not_found(self) -> None:
        with (
            patch(
                "plushie.binary.subprocess.run",
                side_effect=FileNotFoundError("rustc"),
            ),
            pytest.raises(RuntimeError, match="rustc not found"),
        ):
            check_rust_version()

    def test_unparseable_version(self) -> None:
        result = subprocess.CompletedProcess(
            args=["rustc", "--version"],
            returncode=0,
            stdout="rustc unknown",
            stderr="",
        )
        with (
            patch("plushie.binary.subprocess.run", return_value=result),
            pytest.raises(RuntimeError, match="could not parse"),
        ):
            check_rust_version()

    def test_nightly_version_accepted(self) -> None:
        result = subprocess.CompletedProcess(
            args=["rustc", "--version"],
            returncode=0,
            stdout="rustc 1.93.0-nightly (abc1234 2025-02-15)",
            stderr="",
        )
        with patch("plushie.binary.subprocess.run", return_value=result):
            check_rust_version()

    def test_beta_version_accepted(self) -> None:
        result = subprocess.CompletedProcess(
            args=["rustc", "--version"],
            returncode=0,
            stdout="rustc 1.92.0-beta.3 (abc1234 2025-01-10)",
            stderr="",
        )
        with patch("plushie.binary.subprocess.run", return_value=result):
            check_rust_version()


# -- Download with force and checksum ---------------------------------------


class TestDownloadForce:
    def test_skip_when_exists_and_not_forced(self, tmp_path: Path) -> None:
        with (
            patch("plushie.binary.download_dir", return_value=tmp_path),
            patch(
                "plushie.binary.download_name",
                return_value="plushie-renderer",
            ),
        ):
            existing = tmp_path / "plushie-renderer"
            existing.write_bytes(b"existing binary")

            result = download(version="0.4.0", force=False)
            assert result == str(existing)

    def test_redownload_when_forced(self, tmp_path: Path) -> None:
        with (
            patch("plushie.binary.download_dir", return_value=tmp_path),
            patch(
                "plushie.binary.download_name",
                return_value="plushie-renderer",
            ),
            patch(
                "plushie.binary.release_name",
                return_value="plushie-renderer-linux-x86_64",
            ),
            patch("plushie.binary._download_to_file") as mock_download,
            patch("plushie.binary._verify_checksum") as mock_verify,
            patch("plushie.binary.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            existing = tmp_path / "plushie-renderer"
            existing.write_bytes(b"old binary")

            mock_download.side_effect = lambda url, dest: dest.write_bytes(b"new")

            download(version="0.4.0", force=True)

            mock_download.assert_called_once()
            mock_verify.assert_called_once()

    def test_download_tool_uses_plushie_release_asset(self, tmp_path: Path) -> None:
        with (
            patch("plushie.binary.download_dir", return_value=tmp_path),
            patch("plushie.binary._download_to_file") as mock_download,
            patch("plushie.binary._verify_checksum") as mock_verify,
            patch("plushie.binary.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            mock_download.side_effect = lambda _url, dest: dest.write_bytes(b"tool")

            result = download_tool(version="0.4.0", force=True)

            assert result == str(tmp_path / "plushie")
            assert "plushie-linux-" in mock_download.call_args.args[0]
            mock_verify.assert_called_once()

    def test_download_tool_uses_alternate_release_base_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mirror = tmp_path / "mirror"
        version_dir = mirror / "v0.4.0"
        version_dir.mkdir(parents=True)
        body = b"tool"
        artifact = version_dir / tool_release_name()
        artifact.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        artifact.with_name(artifact.name + ".sha256").write_text(
            f"{digest}  {artifact.name}\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PLUSHIE_RELEASE_BASE_URL", mirror.as_uri())

        with patch("plushie.binary.download_dir", return_value=tmp_path / "bin"):
            result = download_tool(version="0.4.0", force=True)

        assert result == str(tmp_path / "bin" / tool_name())
        assert Path(result).read_bytes() == body

    def test_sync_renderer_uses_source_plushie_tool(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "plushie-rust"
        source.mkdir()
        manifest = source / "Cargo.toml"
        manifest.write_text("[workspace]\n", encoding="utf-8")
        monkeypatch.setenv("PLUSHIE_RUST_SOURCE_PATH", str(source))
        bin_dir = Path("bin")

        with patch("plushie.binary.subprocess.run") as mock_run:

            def fake_run(
                *_args: object, **_kwargs: object
            ) -> subprocess.CompletedProcess[bytes]:
                bin_dir.mkdir(exist_ok=True)
                (bin_dir / tool_name()).write_bytes(b"tool")
                (bin_dir / download_name()).write_bytes(b"renderer")
                (bin_dir / launcher_name()).write_bytes(b"launcher")
                return subprocess.CompletedProcess(args=[], returncode=0)

            mock_run.side_effect = fake_run

            result = sync_renderer_with_tool(version="0.4.0")

        args = mock_run.call_args.args[0]
        assert args[:9] == [
            "cargo",
            "run",
            "--manifest-path",
            str(manifest),
            "-p",
            "cargo-plushie",
            "--bin",
            "plushie",
            "--release",
        ]
        assert args[-4:] == ["tools", "sync", "--required-version", "0.4.0"]
        assert result == str(Path("bin") / download_name())

    def test_sync_renderer_requires_renderer_and_launcher_outputs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "plushie-rust"
        source.mkdir()
        (source / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
        monkeypatch.setenv("PLUSHIE_RUST_SOURCE_PATH", str(source))

        with patch("plushie.binary.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

            with pytest.raises(RuntimeError, match="did not install"):
                sync_renderer_with_tool(version="0.4.0")

    def test_default_download_bootstraps_tool_and_renderer_from_file_mirror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plushie.__main__ import main

        mirror = tmp_path / "mirror"
        version_dir = mirror / "v0.4.0"
        version_dir.mkdir(parents=True)

        renderer_body = b"renderer"
        renderer_asset = version_dir / release_name()
        renderer_asset.write_bytes(renderer_body)
        write_checksum(renderer_asset)

        launcher_body = b"launcher"
        launcher_release = tool_release_name().replace(
            "plushie-", "plushie-launcher-", 1
        )
        launcher_name = tool_name().replace("plushie", "plushie-launcher", 1)
        launcher_asset = version_dir / launcher_release
        launcher_asset.write_bytes(launcher_body)
        write_checksum(launcher_asset)

        tool_script = f"""#!/usr/bin/env python3
import hashlib
import os
import pathlib
import stat
import sys
import urllib.parse

args = sys.argv[1:]
if args[:3] != ["tools", "sync", "--required-version"]:
    raise SystemExit(f"unexpected args: {{args!r}}")

version = args[3]
base = os.environ["PLUSHIE_RELEASE_BASE_URL"].rstrip("/")
parsed = urllib.parse.urlparse(base)
if parsed.scheme != "file":
    raise SystemExit(f"expected file mirror, got {{base}}")

root = pathlib.Path(urllib.parse.unquote(parsed.path))

for release_name, local_name in [
    ("{release_name()}", "{download_name()}"),
    ("{launcher_release}", "{launcher_name}"),
]:
    asset = root / f"v{{version}}" / release_name
    checksum = asset.with_name(asset.name + ".sha256")
    body = asset.read_bytes()
    expected = checksum.read_text(encoding="utf-8").split()[0]
    if hashlib.sha256(body).hexdigest() != expected:
        raise SystemExit(f"{{local_name}} checksum mismatch")

    dest = pathlib.Path("bin") / local_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
"""
        tool_asset = version_dir / tool_release_name()
        tool_asset.write_text(tool_script, encoding="utf-8")
        write_checksum(tool_asset)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PLUSHIE_RELEASE_BASE_URL", mirror.as_uri())
        monkeypatch.setattr(
            sys,
            "argv",
            ["python", "download", "--version", "0.4.0", "--force"],
        )

        main()

        installed_tool = tmp_path / "bin" / tool_name()
        installed_renderer = tmp_path / "bin" / download_name()
        installed_launcher = tmp_path / "bin" / launcher_name
        assert installed_tool.is_file()
        assert installed_renderer.read_bytes() == renderer_body
        assert installed_launcher.read_bytes() == launcher_body


class TestDownloadVersionValidation:
    @pytest.mark.parametrize(
        "version",
        [
            "v0.6.1",
            "../0.6.1",
            "0.6.1/asset",
            "0.6.1?x=1",
            "0.6",
            "0.6.1\nother",
            "",
        ],
    )
    def test_download_rejects_malformed_version(
        self, tmp_path: Path, version: str
    ) -> None:
        with (
            patch("plushie.binary.download_dir", return_value=tmp_path),
            patch("plushie.binary._download_to_file") as mock_download,
            pytest.raises(ValueError, match="invalid plushie release version"),
        ):
            download(version=version, force=True)

        mock_download.assert_not_called()

    def test_download_accepts_prerelease_and_build_metadata(
        self, tmp_path: Path
    ) -> None:
        with (
            patch("plushie.binary.download_dir", return_value=tmp_path),
            patch(
                "plushie.binary.release_name",
                return_value="plushie-renderer-linux-x86_64",
            ),
            patch("plushie.binary._download_to_file") as mock_download,
            patch("plushie.binary._verify_checksum"),
            patch("plushie.binary.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            mock_download.side_effect = lambda url, dest: dest.write_bytes(b"binary")

            download(version="0.6.1-rc.1+build.5", force=True)

        url = mock_download.call_args.args[0]
        assert "/v0.6.1-rc.1+build.5/plushie-renderer-linux-x86_64" in url


class TestDownloadWasmForce:
    def test_skip_when_exists_and_not_forced(self, tmp_path: Path) -> None:
        with patch("plushie.binary.wasm_dir", return_value=tmp_path):
            (tmp_path / "plushie_renderer_wasm.js").write_text("js")
            (tmp_path / "plushie_renderer_wasm_bg.wasm").write_bytes(b"wasm")

            result = download_wasm(version="0.4.0", force=False)
            assert result == str(tmp_path)

    def test_redownload_when_forced(self, tmp_path: Path) -> None:
        with (
            patch("plushie.binary.wasm_dir", return_value=tmp_path),
            patch("plushie.binary._download_to_file") as mock_download,
            patch("plushie.binary._verify_checksum") as mock_verify,
            patch("plushie.binary.tarfile.open") as mock_taropen,
        ):
            (tmp_path / "plushie_renderer_wasm.js").write_text("js")
            (tmp_path / "plushie_renderer_wasm_bg.wasm").write_bytes(b"wasm")

            mock_download.side_effect = lambda _url, dest: dest.write_bytes(b"fake tar")
            mock_tf = MagicMock()
            mock_taropen.return_value.__enter__ = lambda s: mock_tf
            mock_taropen.return_value.__exit__ = MagicMock(return_value=False)

            download_wasm(version="0.4.0", force=True)

            mock_download.assert_called_once()
            mock_verify.assert_called_once()


class TestDownloadWasmVersionValidation:
    @pytest.mark.parametrize("version", ["v0.6.1", "../0.6.1", "0.6.1/asset"])
    def test_download_wasm_rejects_malformed_version(
        self, tmp_path: Path, version: str
    ) -> None:
        with (
            patch("plushie.binary.wasm_dir", return_value=tmp_path),
            patch("plushie.binary._download_to_file") as mock_download,
            pytest.raises(ValueError, match="invalid plushie release version"),
        ):
            download_wasm(version=version, force=True)

        mock_download.assert_not_called()

    def test_download_wasm_accepts_prerelease_and_build_metadata(
        self, tmp_path: Path
    ) -> None:
        with (
            patch("plushie.binary.wasm_dir", return_value=tmp_path),
            patch("plushie.binary._download_to_file") as mock_download,
            patch("plushie.binary._verify_checksum"),
            patch("plushie.binary.tarfile.open") as mock_taropen,
        ):
            mock_download.side_effect = lambda _url, dest: dest.write_bytes(b"fake tar")
            mock_tf = MagicMock()
            mock_taropen.return_value.__enter__ = lambda s: mock_tf
            mock_taropen.return_value.__exit__ = MagicMock(return_value=False)

            download_wasm(version="0.6.1-rc.1+build.5", force=True)

        url = mock_download.call_args.args[0]
        assert "/v0.6.1-rc.1+build.5/plushie-renderer-wasm.tar.gz" in url


# -- build_wasm release flag ------------------------------------------------


class TestBuildWasmRelease:
    def test_debug_by_default(self, tmp_path: Path) -> None:
        wasm_crate = tmp_path / "crates" / "plushie-renderer-wasm"
        wasm_crate.mkdir(parents=True)
        (wasm_crate / "pkg").mkdir()

        with (
            patch(
                "plushie.binary.subprocess.run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, "", ""),
                    subprocess.CompletedProcess([], 0, "", ""),
                ],
            ) as mock_run,
            patch("plushie.binary.wasm_dir", return_value=tmp_path / "out"),
        ):
            build_wasm(source_path=str(tmp_path), release=False)

            build_call = mock_run.call_args_list[1]
            assert "--dev" in build_call.args[0]
            assert "--release" not in build_call.args[0]

    def test_release_flag(self, tmp_path: Path) -> None:
        wasm_crate = tmp_path / "crates" / "plushie-renderer-wasm"
        wasm_crate.mkdir(parents=True)
        (wasm_crate / "pkg").mkdir()

        with (
            patch(
                "plushie.binary.subprocess.run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, "", ""),
                    subprocess.CompletedProcess([], 0, "", ""),
                ],
            ) as mock_run,
            patch("plushie.binary.wasm_dir", return_value=tmp_path / "out"),
        ):
            build_wasm(source_path=str(tmp_path), release=True)

            build_call = mock_run.call_args_list[1]
            assert "--release" in build_call.args[0]
            assert "--dev" not in build_call.args[0]


# -- CLI argument parsing ---------------------------------------------------


class TestCliParser:
    """Verify the argparse definitions wire up the new flags."""

    def _parse(self, *argv: str) -> object:
        from plushie.__main__ import _build_parser

        return _build_parser().parse_args(list(argv))

    def test_download_force(self) -> None:
        args = self._parse("download", "--force")
        assert args.force is True  # type: ignore[union-attr]

    def test_download_no_force_default(self) -> None:
        args = self._parse("download")
        assert args.force is False  # type: ignore[union-attr]

    def test_download_bin_and_wasm(self) -> None:
        args = self._parse("download", "--bin", "--wasm")
        assert vars(args)["bin"] is True
        assert args.wasm is True  # type: ignore[union-attr]

    def test_download_bin_only(self) -> None:
        args = self._parse("download", "--bin")
        assert vars(args)["bin"] is True
        assert args.wasm is False  # type: ignore[union-attr]

    def test_build_release(self) -> None:
        args = self._parse("build", "--release")
        assert args.release is True  # type: ignore[union-attr]

    def test_build_no_release_default(self) -> None:
        args = self._parse("build")
        assert args.release is False  # type: ignore[union-attr]

    def test_build_verbose(self) -> None:
        args = self._parse("build", "--verbose")
        assert args.verbose is True  # type: ignore[union-attr]

    def test_build_bin_and_wasm(self) -> None:
        args = self._parse("build", "--bin", "--wasm")
        assert vars(args)["bin"] is True
        assert args.wasm is True  # type: ignore[union-attr]
