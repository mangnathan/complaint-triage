from __future__ import annotations

import io
import urllib.error
from pathlib import Path
from typing import BinaryIO

import pytest

from complaint_triage.data.download import DownloadError, Opener, download, open_https


def serving(payload: bytes) -> Opener:
    def opener(url: str, timeout: float) -> BinaryIO:
        return io.BytesIO(payload)

    return opener


def failing(times: int) -> Opener:
    """Échoue `times` fois, puis renvoie b"ok"."""
    calls = 0

    def opener(url: str, timeout: float) -> BinaryIO:
        nonlocal calls
        calls += 1
        if calls <= times:
            raise urllib.error.URLError("connexion perdue")
        return io.BytesIO(b"ok")

    return opener


def test_writes_the_downloaded_content(tmp_path: Path) -> None:
    dest = tmp_path / "raw" / "file.zip"
    download("https://example.org/file.zip", dest, opener=serving(b"content"))
    assert dest.read_bytes() == b"content"


def test_does_not_download_again_when_file_exists(tmp_path: Path) -> None:
    dest = tmp_path / "file.zip"
    dest.write_bytes(b"already here")

    def must_not_be_called(url: str, timeout: float) -> BinaryIO:
        raise AssertionError("le fichier existe déjà, aucun téléchargement attendu")

    download("https://example.org/file.zip", dest, opener=must_not_be_called)
    assert dest.read_bytes() == b"already here"


def test_retries_after_a_network_error(tmp_path: Path) -> None:
    dest = tmp_path / "file.zip"
    download("https://example.org/f", dest, opener=failing(times=2), backoff_seconds=0)
    assert dest.read_bytes() == b"ok"


def test_leaves_no_partial_file_when_all_attempts_fail(tmp_path: Path) -> None:
    dest = tmp_path / "file.zip"
    with pytest.raises(DownloadError):
        download("https://example.org/f", dest, opener=failing(times=5), backoff_seconds=0)
    assert list(tmp_path.iterdir()) == []


def test_refuses_plain_http() -> None:
    with pytest.raises(ValueError, match="https"):
        open_https("http://example.org/file.zip", timeout=1)
