"""Étude de faisabilité v0.0 : chiffres clés de la base CFPB sur le périmètre banque de détail.

Reproduit les tableaux cités dans docs/v0.0-cadrage/v0.0-rapport-de-cadrage.md :
- séries mensuelles (volume, réponses des entreprises) via l'API publique ;
- couverture des récits clients dans l'archive FOIA.

Usage : python scripts/feasibility/collect_cfpb_feasibility_stats.py --out docs/v0.0-cadrage/data
"""

from __future__ import annotations

import argparse
import calendar
import json
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

API_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
ARCHIVE_URL = "https://files.consumerfinance.gov/f/documents/"

# "Credit card or prepaid card" a été scindé en 2023 : on garde l'ancien libellé pour la continuité.
SCOPE_PRODUCTS_API = ("Credit card", "Credit card or prepaid card", "Checking or savings account")
SCOPE_PRODUCTS_ARCHIVE = ("Credit card", "Checking or savings account")
RESPONSES = (
    "Closed with monetary relief",
    "Closed with non-monetary relief",
    "Closed with explanation",
    "In progress",
    "Untimely response",
)
ARCHIVE_SAMPLES = {
    "2025-03/04": "CCDB_Export_10_March_2025_through_April_2025",
    "2026-07": "CCDB_Export_20_July_2026",
    "2026-08": "CCDB_Export_21_August_2026",
}


@dataclass(frozen=True)
class MonthStats:
    month: str
    total: int
    responses: dict[str, int]


def _get_json(params: list[tuple[str, str]]) -> dict[str, Any]:
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        return cast(dict[str, Any], json.load(resp))


def fetch_month(year: int, month: int) -> MonthStats:
    last_day = calendar.monthrange(year, month)[1]
    params = [("product", p) for p in SCOPE_PRODUCTS_API] + [
        ("size", "0"),
        ("date_received_min", f"{year}-{month:02d}-01"),
        ("date_received_max", f"{year}-{month:02d}-{last_day}"),
    ]
    payload = _get_json(params)
    agg = payload["aggregations"]["company_response"]
    buckets = agg.get("company_response", agg)["buckets"]
    counts = {b["key"]: b["doc_count"] for b in buckets}
    return MonthStats(
        month=f"{year}-{month:02d}",
        total=payload["hits"]["total"]["value"],
        responses={r: counts.get(r, 0) for r in RESPONSES},
    )


def monthly_series(start_year: int, end_year: int, end_month: int) -> pd.DataFrame:
    rows = []
    for year in range(start_year, end_year + 1):
        last_month = end_month if year == end_year else 12
        for month in range(1, last_month + 1):
            stats = fetch_month(year, month)
            rows.append({"month": stats.month, "total": stats.total, **stats.responses})
    return pd.DataFrame(rows)


def narrative_coverage(download_dir: Path) -> pd.DataFrame:
    download_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, name in ARCHIVE_SAMPLES.items():
        target = download_dir / f"{name}.zip"
        if not target.exists():
            urllib.request.urlretrieve(f"{ARCHIVE_URL}{name}.zip", target)
        with zipfile.ZipFile(target) as zf:
            df = pd.read_csv(
                zf.open(zf.namelist()[0]),
                usecols=["Product", "Consumer complaint narrative"],
                low_memory=False,
            )
        scope = df[df["Product"].isin(SCOPE_PRODUCTS_ARCHIVE)]
        narratives = scope["Consumer complaint narrative"].dropna()
        rows.append(
            {
                "period": label,
                "rows_all": len(df),
                "rows_scope": len(scope),
                "narrative_share_scope": round(len(narratives) / max(len(scope), 1), 3),
                "median_words": int(narratives.str.count(r"\S+").median())
                if len(narratives)
                else None,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("docs/v0.0-cadrage/data"))
    parser.add_argument("--downloads", type=Path, default=Path("data/raw/archive"))
    parser.add_argument("--end", default="2026-10", help="dernier mois inclus, AAAA-MM")
    args = parser.parse_args()

    end_year, end_month = (int(x) for x in args.end.split("-"))
    args.out.mkdir(parents=True, exist_ok=True)
    monthly_series(2022, end_year, end_month).to_csv(
        args.out / "series-mensuelles-perimetre-bancaire.csv", index=False
    )
    narrative_coverage(args.downloads).to_csv(
        args.out / "couverture-des-recits-archive-foia.csv", index=False
    )


if __name__ == "__main__":
    main()
