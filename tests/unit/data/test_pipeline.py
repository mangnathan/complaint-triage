from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from complaint_triage.data.pipeline import (
    attach_narratives,
    build_dataset,
    drop_rows_without_issue,
    read_export,
    read_narratives,
)
from complaint_triage.data.schema import validate_complaints
from complaint_triage.data.sources import EXPORT_URL

START = date(2022, 1, 1)


def test_read_export_keeps_scope_and_harmonizes_legacy_cards(export_zip: Path) -> None:
    df = read_export(export_zip, START)

    # 3 : carte prépayée ; 4 : crédit immobilier ; 5 : reçue avant la date de début.
    assert sorted(df["complaint_id"]) == [1, 2, 6, 7]
    assert df.set_index("complaint_id").loc[2, "product"] == "Credit card"
    assert df["date_received"].dtype == "datetime64[ns]"


def test_rows_without_issue_are_dropped_and_counted(export_zip: Path) -> None:
    kept, dropped = drop_rows_without_issue(read_export(export_zip, START))

    assert dropped == 1
    assert 7 not in set(kept["complaint_id"])


def test_read_narratives_filters_ids_drops_empty_and_keeps_last_version(
    archive_zip: Path,
) -> None:
    narratives = read_narratives([archive_zip], complaint_ids={1, 2, 6})

    assert narratives.to_dict("records") == [{"complaint_id": 1, "narrative": "Corrected story."}]


def test_attach_narratives_keeps_complaints_without_story(
    export_zip: Path, archive_zip: Path
) -> None:
    complaints = read_export(export_zip, START)
    narratives = read_narratives([archive_zip], set(complaints["complaint_id"]))

    merged = attach_narratives(complaints, narratives)

    assert len(merged) == len(complaints)
    assert merged["narrative"].notna().sum() == 1


def test_build_dataset_writes_validated_parquet_and_manifest(
    tmp_path: Path, export_bytes: bytes, archive_bytes: bytes
) -> None:
    def fake_opener(url: str, timeout: float) -> BinaryIO:
        return io.BytesIO(export_bytes if url == EXPORT_URL else archive_bytes)

    out = build_dataset(tmp_path, START, opener=fake_opener)

    dataset = pd.read_parquet(out)
    validate_complaints(dataset)
    assert sorted(dataset["complaint_id"]) == [1, 2, 6]

    manifest = json.loads(out.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert manifest["rows"] == 3
    assert manifest["rows_with_narrative"] == 1
    assert manifest["rows_dropped_without_issue"] == 1
    assert manifest["sources"][0]["url"] == EXPORT_URL
    assert all(len(source["sha256"]) == 64 for source in manifest["sources"])
