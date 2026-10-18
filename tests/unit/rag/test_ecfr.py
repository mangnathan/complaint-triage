from __future__ import annotations

import gzip
import io
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

import pytest

from complaint_triage.rag.ecfr import (
    RegulationPart,
    download_parts,
    open_ecfr,
    parse_sections,
    read_xml_bytes,
    reader_url,
)

PART = RegulationPart(1005, "Regulation E", ((1, 20),))
XML = """<?xml version="1.0" encoding="UTF-8"?>
<DIV5 N="1005" TYPE="PART">
  <DIV8 N="1005.11" TYPE="SECTION">
    <HEAD>§ 1005.11 Procedures for resolving errors.</HEAD>
    <P>(a) <I>Definition of error</I>—(1) The term “error” means:</P>
    <P>(i) An unauthorized electronic fund transfer;</P>
  </DIV8>
  <DIV8 N="1005.30" TYPE="SECTION">
    <HEAD>§ 1005.30 Remittance transfer definitions.</HEAD>
    <P>(a) Out of scope.</P>
  </DIV8>
</DIV5>
""".encode()


def test_only_the_selected_sections_are_kept() -> None:
    sections = parse_sections(XML, PART)

    assert [s.number for s in sections] == ["1005.11"]
    assert sections[0].heading == "§ 1005.11 Procedures for resolving errors."
    assert sections[0].paragraphs[0] == "(a) Definition of error—(1) The term “error” means:"


def test_another_part_is_never_kept() -> None:
    assert not PART.keeps("1026.13")
    assert not PART.keeps("1005.11a")


def test_compressed_and_plain_files_are_both_read(tmp_path: Path) -> None:
    (tmp_path / "plain").write_bytes(XML)
    (tmp_path / "gzip").write_bytes(gzip.compress(XML))

    assert read_xml_bytes(tmp_path / "plain") == XML
    assert read_xml_bytes(tmp_path / "gzip") == XML


def test_an_xml_bomb_is_refused() -> None:
    bomb = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>
<DIV5>&lol2;</DIV5>"""

    with pytest.raises(Exception, match="(?i)entit"):
        parse_sections(bomb, PART)


def test_reader_url_points_to_the_cited_paragraph() -> None:
    url = reader_url("1005.11", "(c)", on_date="2026-10-15")

    assert url == "https://www.ecfr.gov/on/2026-10-15/title-12/section-1005.11#p-1005.11(c)"


def test_only_https_is_accepted() -> None:
    with pytest.raises(ValueError, match="https"):
        open_ecfr("http://www.ecfr.gov/api", 10)


def test_each_part_is_downloaded_once(tmp_path: Path) -> None:
    calls: list[str] = []

    @contextmanager
    def fake_opener(url: str, timeout: float) -> Iterator[BinaryIO]:
        calls.append(url)
        yield io.BytesIO(gzip.compress(XML))

    first = download_parts(tmp_path, on_date="2026-10-15", opener=fake_opener)
    download_parts(tmp_path, on_date="2026-10-15", opener=fake_opener)

    assert len(calls) == 3  # une fois par partie, pas une fois de plus au second appel
    assert read_xml_bytes(first[1005]) == XML
