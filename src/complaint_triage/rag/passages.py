"""Découpage des sections en passages citables : un passage par paragraphe de premier niveau.

Un paragraphe de premier niveau commence par une lettre entre parenthèses, « (a) », « (b) »...
La citation d'un passage, « 12 CFR 1005.11(b) », renvoie donc à un endroit précis du texte que
n'importe qui peut ouvrir sur le site de l'eCFR.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import pandas as pd

from complaint_triage.rag.ecfr import CORPUS_DATE, ECFR_TITLE, RegulationPart, Section, reader_url

# Au-delà, un paragraphe est coupé en plusieurs passages, à la limite d'un alinéa.
MAX_WORDS = 350
_TOP_LEVEL = re.compile(r"^\(([a-z])\)\s")
# Ces lettres sont aussi des chiffres romains : « (i) » ouvre souvent une sous-liste.
_ROMAN_LETTERS = frozenset("ivx")
# Un paragraphe de premier niveau porte presque toujours un titre : « (b) Notice of error— ».
_RESERVED = re.compile(r"(\([a-z]\)\s*)?\[Reserved\]\.?")
_HEADED = re.compile(r"^\([a-z]\)\s+[A-Z][^.—]{0,80}(—|\.\s)")


@dataclass(frozen=True)
class Passage:
    passage_id: str
    citation: str
    regulation: str
    section: str
    heading: str
    text: str
    url: str


def top_level_letter(paragraph: str, previous: str | None) -> str | None:
    """Lettre du paragraphe s'il ouvre un paragraphe de premier niveau, sinon None.

    La lettre doit suivre la précédente dans l'alphabet. Pour i, v et x, qui sont aussi des
    chiffres romains, le paragraphe doit en plus porter un titre.
    """
    match = _TOP_LEVEL.match(paragraph)
    if match is None:
        return None
    letter = match.group(1)
    expected = "a" if previous is None else chr(ord(previous) + 1)
    if letter != expected:
        return None
    if letter in _ROMAN_LETTERS and not _HEADED.match(paragraph):
        return None
    return letter


def _groups(section: Section) -> list[tuple[str | None, list[str]]]:
    """Paragraphes regroupés par lettre de premier niveau ; None pour le texte d'introduction."""
    groups: list[tuple[str | None, list[str]]] = [(None, [])]
    current: str | None = None
    for paragraph in section.paragraphs:
        letter = top_level_letter(paragraph, current)
        if letter is not None:
            current = letter
            groups.append((letter, []))
        groups[-1][1].append(paragraph)
    return [(letter, paragraphs) for letter, paragraphs in groups if paragraphs]


def _windows(paragraphs: list[str], max_words: int) -> list[str]:
    """Regroupe les alinéas sans dépasser `max_words`, sauf si un alinéa seul les dépasse."""
    windows: list[list[str]] = [[]]
    words = 0
    for paragraph in paragraphs:
        size = len(paragraph.split())
        if windows[-1] and words + size > max_words:
            windows.append([])
            words = 0
        windows[-1].append(paragraph)
        words += size
    return ["\n".join(window) for window in windows]


def section_passages(
    section: Section,
    part: RegulationPart,
    *,
    max_words: int = MAX_WORDS,
    on_date: str = CORPUS_DATE,
) -> list[Passage]:
    passages = []
    for letter, paragraphs in _groups(section):
        if _RESERVED.fullmatch(" ".join(paragraphs)):
            continue  # paragraphe abrogé, sans contenu à citer
        anchor = f"({letter})" if letter else None
        citation = f"{ECFR_TITLE} CFR {section.number}{anchor or ''}"
        windows = _windows(paragraphs, max_words)
        for index, text in enumerate(windows, start=1):
            suffix = f"-{index}" if len(windows) > 1 else ""
            passages.append(
                Passage(
                    passage_id=f"{section.number}{anchor or ''}{suffix}",
                    citation=citation,
                    regulation=part.regulation,
                    section=section.number,
                    heading=section.heading,
                    text=text,
                    url=reader_url(section.number, anchor, on_date),
                )
            )
    return passages


def passages_frame(passages: list[Passage]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(p) for p in passages])
    if frame["passage_id"].duplicated().any():
        raise ValueError("Deux passages ont le même identifiant.")
    return frame
