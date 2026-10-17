from __future__ import annotations

import pandas as pd

from complaint_triage.data.taxonomy import harmonize_product


def harmonize(product: str, sub_product: str | None) -> str:
    result = harmonize_product(pd.Series([product]), pd.Series([sub_product]))
    return str(result.iloc[0])


def test_legacy_credit_card_becomes_credit_card() -> None:
    assert harmonize("Credit card or prepaid card", "Store credit card") == "Credit card"
    assert (
        harmonize("Credit card or prepaid card", "General-purpose credit card or charge card")
        == "Credit card"
    )


def test_legacy_prepaid_products_become_prepaid_card() -> None:
    assert harmonize("Credit card or prepaid card", "Gift card") == "Prepaid card"
    assert harmonize("Credit card or prepaid card", "Payroll card") == "Prepaid card"


def test_legacy_without_sub_product_is_not_counted_as_credit_card() -> None:
    assert harmonize("Credit card or prepaid card", None) == "Prepaid card"


def test_current_products_are_unchanged() -> None:
    assert harmonize("Credit card", "Store credit card") == "Credit card"
    assert harmonize("Mortgage", "FHA mortgage") == "Mortgage"
