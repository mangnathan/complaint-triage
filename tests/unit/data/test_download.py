from __future__ import annotations

import io
import urllib.error
from email.message import Message
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


class _ResponseWithLength(io.BytesIO):
    """Réponse dont le serveur annonce une taille, comme un vrai en-tête Content-Length."""

    def __init__(self, payload: bytes, announced: int) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(announced)}


def test_rejects_a_file_shorter_than_announced(tmp_path: Path) -> None:
    dest = tmp_path / "file.zip"

    def truncated(url: str, timeout: float) -> BinaryIO:
        return _ResponseWithLength(b"half", announced=8)

    with pytest.raises(DownloadError):
        download("https://example.org/f", dest, opener=truncated, backoff_seconds=0)
    assert list(tmp_path.iterdir()) == []


def test_accepts_a_file_of_the_announced_size(tmp_path: Path) -> None:
    dest = tmp_path / "file.zip"

    def complete(url: str, timeout: float) -> BinaryIO:
        return _ResponseWithLength(b"complete", announced=8)

    download("https://example.org/f", dest, opener=complete)
    assert dest.read_bytes() == b"complete"


def test_does_not_retry_a_missing_file(tmp_path: Path) -> None:
    calls = 0

    def not_found(url: str, timeout: float) -> BinaryIO:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(url, 404, "Not Found", Message(), None)

    with pytest.raises(DownloadError, match="introuvable"):
        download("https://example.org/f", tmp_path / "f.zip", opener=not_found, backoff_seconds=0)
    assert calls == 1


def test_unexpected_error_leaves_no_partial_file(tmp_path: Path) -> None:
    class _BrokenStream(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise OSError("disque plein")

    def broken(url: str, timeout: float) -> BinaryIO:
        return _BrokenStream(b"")

    with pytest.raises(OSError, match="disque plein"):
        download("https://example.org/f", tmp_path / "f.zip", opener=broken)
    assert list(tmp_path.iterdir()) == []


def test_refuses_plain_http() -> None:
    with pytest.raises(ValueError, match="https"):
        open_https("http://example.org/file.zip", timeout=1)
