from __future__ import annotations

import json
from typing import Any

import pytest

from complaint_triage.rag.answer import (
    ANSWERED,
    REFUSED,
    answer_question,
    build_prompt,
    validate_question,
    verify,
)
from complaint_triage.rag.retrieval import Hit

PASSAGES = {
    "1005.11(c)-1": {
        "passage_id": "1005.11(c)-1",
        "citation": "12 CFR 1005.11(c)",
        "heading": "§ 1005.11 Procedures for resolving errors.",
        "text": "(c) Time limits and extent of investigation—(1) Ten-business-day rule. "
        "A financial institution shall investigate promptly and determine whether an error "
        "occurred within 10 business days of receiving a notice of error.",
        "url": "https://www.ecfr.gov/on/2026-10-15/title-12/section-1005.11#p-1005.11(c)",
    },
    "1005.6(b)-1": {
        "passage_id": "1005.6(b)-1",
        "citation": "12 CFR 1005.6(b)",
        "heading": "§ 1005.6 Liability of consumer for unauthorized transfers.",
        "text": "(b) Limitations on amount of liability. The consumer's liability shall not exceed "
        "the lesser of $50 or the amount of unauthorized transfers.",
        "url": "https://www.ecfr.gov/on/2026-10-15/title-12/section-1005.6#p-1005.6(b)",
    },
}
QUOTE = "shall investigate promptly and determine whether an error occurred"


class FixedRetriever:
    def search(self, query: str, k: int) -> list[Hit]:
        return [Hit("1005.11(c)-1", 0.9), Hit("1005.6(b)-1", 0.5)][:k]


class FakeModel:
    name = "fake"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def generate(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        self.prompts.append(prompt)
        return self.reply


def reply(**fields: Any) -> str:
    base = {"answerable": True, "answer": "", "citations": [], "refusal_reason": ""}
    return json.dumps({**base, **fields})


def test_a_verified_answer_keeps_its_sources() -> None:
    model = FakeModel(
        reply(
            answer="The bank must investigate within 10 business days.",
            citations=[{"passage_id": "1005.11(c)-1", "quote": QUOTE}],
        )
    )

    answer = answer_question("How long to investigate?", FixedRetriever(), PASSAGES, model)

    assert answer.status == ANSWERED
    assert answer.sources[0].citation == "12 CFR 1005.11(c)"
    assert answer.sources[0].url.endswith("#p-1005.11(c)")
    assert answer.retrieved == ("1005.11(c)-1", "1005.6(b)-1")


def test_a_quote_that_is_not_in_the_passage_is_refused() -> None:
    response = {
        "answerable": True,
        "answer": "The bank has 30 days.",
        "citations": [
            {"passage_id": "1005.11(c)-1", "quote": "the bank has thirty days to decide"}
        ],
    }

    assert verify(response, PASSAGES).status == REFUSED


def test_a_citation_of_a_passage_not_provided_is_refused() -> None:
    response = {
        "answerable": True,
        "answer": "Something.",
        "citations": [{"passage_id": "1026.13(c)", "quote": QUOTE}],
    }

    answer = verify(response, PASSAGES)

    assert answer.status == REFUSED
    assert "non fourni" in answer.reason


def test_one_bad_citation_is_enough_to_refuse_the_whole_answer() -> None:
    response = {
        "answerable": True,
        "answer": "Two facts.",
        "citations": [
            {"passage_id": "1005.11(c)-1", "quote": QUOTE},
            {"passage_id": "1005.6(b)-1", "quote": "liability shall never exceed $500"},
        ],
    }

    assert verify(response, PASSAGES).status == REFUSED


def test_an_answer_without_citation_is_refused() -> None:
    assert (
        verify({"answerable": True, "answer": "Yes.", "citations": []}, PASSAGES).status == REFUSED
    )


def test_a_too_short_quote_proves_nothing() -> None:
    response = {
        "answerable": True,
        "answer": "Yes.",
        "citations": [{"passage_id": "1005.6(b)-1", "quote": "$50"}],
    }

    assert verify(response, PASSAGES).status == REFUSED


def test_typographic_quotes_and_spaces_do_not_break_the_check() -> None:
    passages = {
        "p": {
            **PASSAGES["1005.6(b)-1"],
            "text": "The term “error”   means an unauthorized transfer.",
        }
    }
    response = {
        "answerable": True,
        "answer": "Definition.",
        "citations": [{"passage_id": "p", "quote": 'The term "error" means an unauthorized'}],
    }

    assert verify(response, passages).status == ANSWERED


def test_the_model_may_refuse_with_a_reason() -> None:
    model = FakeModel(reply(answerable=False, refusal_reason="Nothing about mortgages."))

    answer = answer_question("Mortgage escrow rules?", FixedRetriever(), PASSAGES, model)

    assert answer.status == REFUSED
    assert answer.reason == "Nothing about mortgages."


def test_an_unreadable_reply_is_refused() -> None:
    answer = answer_question("Question?", FixedRetriever(), PASSAGES, FakeModel("not json"))

    assert answer.status == REFUSED


def test_the_prompt_contains_only_the_retrieved_passages() -> None:
    model = FakeModel(reply(answerable=False))

    answer_question("Question?", FixedRetriever(), PASSAGES, model, k=1)

    assert "[1005.11(c)-1]" in model.prompts[0]
    assert "1005.6(b)-1" not in model.prompts[0]


def test_questions_are_cleaned_and_checked() -> None:
    assert validate_question("  How long\x00 to   investigate? ") == "How long to investigate?"
    with pytest.raises(ValueError, match="vide"):
        validate_question(" \x07 ")
    with pytest.raises(ValueError, match="dépasse"):
        validate_question("a" * 1001)


def test_build_prompt_labels_each_passage_with_its_id() -> None:
    prompt = build_prompt("Q?", [PASSAGES["1005.6(b)-1"]])

    assert prompt.startswith("Passages:")
    assert "[1005.6(b)-1] 12 CFR 1005.6(b)" in prompt
    assert prompt.endswith("Question: Q?")
