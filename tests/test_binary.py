"""Tests for binary resolution, download, and build helpers."""

from __future__ import annotations

import hashlib
import subprocess
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
    download_wasm,
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
        assert download_name(os_name="linux", arch="x86_64") == "plushie-linux-x86_64"

    def test_windows_gets_exe(self) -> None:
        name = download_name(os_name="windows", arch="x86_64")
        assert name.endswith(".exe")


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
            patch("plushie.binary.download_name", return_value="plushie-linux-x86_64"),
        ):
            existing = tmp_path / "plushie-linux-x86_64"
            existing.write_bytes(b"existing binary")

            result = download(version="0.4.0", force=False)
            assert result == str(existing)

    def test_redownload_when_forced(self, tmp_path: Path) -> None:
        with (
            patch("plushie.binary.download_dir", return_value=tmp_path),
            patch("plushie.binary.download_name", return_value="plushie-linux-x86_64"),
            patch("plushie.binary.urllib.request.urlretrieve") as mock_retrieve,
            patch("plushie.binary._verify_checksum") as mock_verify,
            patch("plushie.binary.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            existing = tmp_path / "plushie-linux-x86_64"
            existing.write_bytes(b"old binary")

            mock_retrieve.side_effect = lambda url, dest: Path(dest).write_bytes(b"new")

            download(version="0.4.0", force=True)

            mock_retrieve.assert_called_once()
            mock_verify.assert_called_once()


class TestDownloadWasmForce:
    def test_skip_when_exists_and_not_forced(self, tmp_path: Path) -> None:
        with patch("plushie.binary.wasm_dir", return_value=tmp_path):
            (tmp_path / "plushie_wasm.js").write_text("js")
            (tmp_path / "plushie_wasm_bg.wasm").write_bytes(b"wasm")

            result = download_wasm(version="0.4.0", force=False)
            assert result == str(tmp_path)

    def test_redownload_when_forced(self, tmp_path: Path) -> None:
        with (
            patch("plushie.binary.wasm_dir", return_value=tmp_path),
            patch("plushie.binary.urllib.request.urlretrieve") as mock_retrieve,
            patch("plushie.binary._verify_checksum") as mock_verify,
            patch("plushie.binary.tarfile.open") as mock_taropen,
        ):
            (tmp_path / "plushie_wasm.js").write_text("js")
            (tmp_path / "plushie_wasm_bg.wasm").write_bytes(b"wasm")

            def fake_retrieve(url: str, dest: str) -> None:
                Path(dest).write_bytes(b"fake tar")

            mock_retrieve.side_effect = fake_retrieve
            mock_tf = MagicMock()
            mock_taropen.return_value.__enter__ = lambda s: mock_tf
            mock_taropen.return_value.__exit__ = MagicMock(return_value=False)

            download_wasm(version="0.4.0", force=True)

            mock_retrieve.assert_called_once()
            mock_verify.assert_called_once()


# -- build_wasm release flag ------------------------------------------------


class TestBuildWasmRelease:
    def test_debug_by_default(self, tmp_path: Path) -> None:
        wasm_crate = tmp_path / "plushie-renderer-wasm"
        wasm_crate.mkdir()
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
        wasm_crate = tmp_path / "plushie-renderer-wasm"
        wasm_crate.mkdir()
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
