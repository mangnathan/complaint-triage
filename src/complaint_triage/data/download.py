"""Téléchargement idempotent et atomique des fichiers sources."""

from __future__ import annotations

import shutil
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import BinaryIO, cast

# Une fonction (url, timeout) -> flux binaire. Remplaçable dans les tests, sans accès réseau.
Opener = Callable[[str, float], AbstractContextManager[BinaryIO]]


class DownloadError(RuntimeError):
    pass


def open_https(url: str, timeout: float) -> AbstractContextManager[BinaryIO]:
    if not url.startswith("https://"):
        raise ValueError(f"URL refusée, seul https est accepté : {url}")
    return cast(AbstractContextManager[BinaryIO], urllib.request.urlopen(url, timeout=timeout))  # noqa: S310


def download(
    url: str,
    dest: Path,
    *,
    opener: Opener = open_https,
    retries: int = 3,
    timeout: float = 120.0,
    backoff_seconds: float = 2.0,
) -> Path:
    """Télécharge `url` vers `dest`, sauf si le fichier existe déjà.

    Le contenu est d'abord écrit dans un fichier `.part`, renommé seulement une fois complet :
    une coupure réseau ne laisse jamais un fichier tronqué que l'on prendrait pour valide.
    """
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with opener(url, timeout) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out)
            partial.replace(dest)
            return dest
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last_error = error
            partial.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)
    raise DownloadError(f"Échec du téléchargement après {retries} essais : {url}") from last_error
