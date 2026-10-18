from __future__ import annotations

import pytest

from complaint_triage.rag.ecfr import RegulationPart, Section
from complaint_triage.rag.passages import passages_frame, section_passages, top_level_letter

PART = RegulationPart(1005, "Regulation E", ((1, 20),))


def section(*paragraphs: str) -> Section:
    return Section("1005.11", "§ 1005.11 Procedures for resolving errors.", paragraphs)


def test_one_passage_per_top_level_paragraph() -> None:
    passages = section_passages(
        section(
            "(a) Definition of error—(1) The term means:",
            "(i) An unauthorized transfer;",
            "(b) Notice of error from consumer—(1) Timing; contents.",
        ),
        PART,
    )

    assert [p.passage_id for p in passages] == ["1005.11(a)", "1005.11(b)"]
    assert passages[0].citation == "12 CFR 1005.11(a)"
    assert "(i) An unauthorized transfer;" in passages[0].text


def test_a_roman_numeral_does_not_open_a_new_paragraph() -> None:
    # Après (h), « (i) » suivi de « (ii) » est le premier élément d'une liste.
    following = ["(ii) An incorrect transfer;", "(j) Next definition."]
    assert top_level_letter("(i) An unauthorized transfer;", "h", following) is None


def test_a_letter_i_followed_by_j_is_a_paragraph_even_without_heading() -> None:
    # Définitions de la Regulation E : « (i) Person means... », puis « (j) ... ».
    following = ["(j) Preauthorized electronic fund transfer means..."]
    assert top_level_letter("(i) Person means a natural person.", "h", following) == "i"


def test_a_v_after_iv_belongs_to_a_list() -> None:
    preceding = ["(u) Tiered-rate account means:", "(iv) A fourth case;"]
    assert top_level_letter("(v) A fifth case;", "u", preceding=preceding) is None


def test_a_last_definition_v_without_iv_is_a_paragraph() -> None:
    # Dernière définition de la Regulation DD : ni « (vi) », ni « (w) » ensuite.
    preceding = ["(u) Tiered-rate account means an account."]
    assert top_level_letter("(v) Variable-rate account means...", "u", preceding=preceding) == "v"


def test_at_the_end_of_a_section_the_heading_decides() -> None:
    assert top_level_letter("(i) Relation to Regulation E. This section...", "h") == "i"
    assert top_level_letter("(i) An unauthorized transfer;", "h") is None


def test_a_letter_followed_directly_by_a_number_opens_a_paragraph() -> None:
    # Les définitions de la Regulation E commencent par « (a)(1) Access device means ».
    assert top_level_letter("(a)(1) Access device means a card.", None) == "a"
    assert top_level_letter("(b) Account means a demand deposit.", "a") == "b"


def test_letters_must_follow_each_other() -> None:
    assert top_level_letter("(c) Time limits— ...", "a") is None
    assert top_level_letter("(b) Notice of error— ...", "a") == "b"


def test_a_long_paragraph_is_split_between_paragraphs_not_inside_them() -> None:
    long = "word " * 200
    passages = section_passages(section(f"(a) Heading— {long}", long, long), PART, max_words=350)

    assert [p.passage_id for p in passages] == ["1005.11(a)-1", "1005.11(a)-2", "1005.11(a)-3"]
    assert {p.citation for p in passages} == {"12 CFR 1005.11(a)"}


def test_reserved_paragraphs_are_dropped() -> None:
    passages = section_passages(
        section("(a) Definition— text.", "(b) [Reserved]", "(c) Time limits— text."), PART
    )

    assert [p.passage_id for p in passages] == ["1005.11(a)", "1005.11(c)"]


def test_introduction_without_letter_is_cited_by_section() -> None:
    passages = section_passages(section("For purposes of this part, the following apply:"), PART)

    assert passages[0].citation == "12 CFR 1005.11"
    assert passages[0].url.endswith("section-1005.11")


def test_duplicate_identifiers_are_refused() -> None:
    passages = section_passages(section("(a) Definition— text."), PART)

    with pytest.raises(ValueError, match="identifiant"):
        passages_frame(passages + passages)
