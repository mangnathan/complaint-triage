"""Données synthétiques au format de l'export et de l'archive du CFPB."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from complaint_triage.data.schema import EXPORT_COLUMNS

EXPORT_ROWS = [
    # (id, date, produit, sous-produit, réponse)
    (1, "2023-03-01", "Credit card", "Store credit card", "Closed with monetary relief"),
    (
        2,
        "2022-05-10",
        "Credit card or prepaid card",
        "Store credit card",
        "Closed with explanation",
    ),
    (3, "2022-05-11", "Credit card or prepaid card", "Gift card", "Closed with explanation"),
    (4, "2024-01-15", "Mortgage", "FHA mortgage", "Closed with explanation"),
    (5, "2021-12-31", "Credit card", "Store credit card", "Closed with explanation"),
    (6, "2025-07-01", "Checking or savings account", "Checking account", "In progress"),
    (7, "2024-04-02", "Checking or savings account", "", "Closed with explanation"),
]
# Fiche incomplète, comme les 5 cas « Referral » observés dans l'export réel.
ID_WITHOUT_ISSUE = 7


def export_frame() -> pd.DataFrame:
    rows = []
    for complaint_id, received, product, sub_product, response in EXPORT_ROWS:
        row = dict.fromkeys(EXPORT_COLUMNS, "")
        row.update(
            {
                "Complaint ID": str(complaint_id),
                "Date received": received,
                "Product": product,
                "Sub-product": sub_product,
                "Issue": ""
                if complaint_id == ID_WITHOUT_ISSUE
                else "Problem with a purchase shown on your statement",
                "Company": "Example Bank",
                "Submitted via": "Web",
                "Date sent to company": received,
                "Company response to consumer": response,
                "Timely response?": "Yes",
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


DEFAULT_COMPLAINT: dict[str, Any] = {
    "date_received": "2024-01-15",
    "product": "Credit card",
    "sub_product": "Store credit card",
    "issue": "Fees or interest",
    "sub_issue": None,
    "company": "Example Bank",
    "state": "CA",
    "zip_code": "90001",
    "tags": None,
    "submitted_via": "Web",
    "date_sent_to_company": "2024-01-16",
    "company_public_response": None,
    "company_response": "Closed with monetary relief",
    "timely_response": "Yes",
    "narrative": None,
}
_DATE_COLUMNS = ("date_received", "date_sent_to_company")


@pytest.fixture
def make_complaints() -> Callable[..., pd.DataFrame]:
    """Construit des réclamations au format du jeu `interim`, une ligne par dictionnaire.

    Chaque dictionnaire ne précise que ce qui change par rapport à DEFAULT_COMPLAINT.
    """

    def build(*overrides: dict[str, Any]) -> pd.DataFrame:
        rows = [
            {"complaint_id": index + 1, **DEFAULT_COMPLAINT, **override}
            for index, override in enumerate(overrides or ({},))
        ]
        df = pd.DataFrame(rows)
        for column in df.columns:
            if column in _DATE_COLUMNS:
                df[column] = pd.to_datetime(df[column]).astype("datetime64[ns]")
            elif column != "complaint_id":
                df[column] = df[column].astype("str")
        return df.astype({"complaint_id": "int64"})

    return build


def zip_csv(df: pd.DataFrame, member: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, df.to_csv(index=False))
    return buffer.getvalue()


def archive_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Complaint ID": ["1", "4", "6", "1"],
            "Product": ["Credit card", "Mortgage", "Checking or savings account", "Credit card"],
            "Consumer complaint narrative": [
                "First version of the story.",
                "Out of scope story.",
                "",
                "Corrected story.",
            ],
        }
    )


@pytest.fixture
def export_bytes() -> bytes:
    return zip_csv(export_frame(), "complaints.csv")


@pytest.fixture
def archive_bytes() -> bytes:
    return zip_csv(archive_frame(), "archive.csv")


@pytest.fixture
def export_zip(tmp_path: Path, export_bytes: bytes) -> Path:
    path = tmp_path / "export.zip"
    path.write_bytes(export_bytes)
    return path


@pytest.fixture
def archive_zip(tmp_path: Path, archive_bytes: bytes) -> Path:
    path = tmp_path / "archive.zip"
    path.write_bytes(archive_bytes)
    return path
