"""Part 0 · Data validation and quality checks."""
from __future__ import annotations

import pandas as pd

from . import config as cfg
from .result import Result

SEGMENT_MISMATCH = "Tx segment ≠ profile segment (% of rows)"
MULTI_SEGMENT = "Users with >1 segment in their transactions"


def run(tx_raw: pd.DataFrame, users: pd.DataFrame, df: pd.DataFrame) -> Result:
    r = Result("quality")

    checks = pd.DataFrame({
        "check": [
            "Transaction rows", "User rows",
            "Empty cells (transactions)", "Empty cells (users)",
            "Duplicate transaction_id", "Duplicate user_id",
            "Transactions with unknown user",
            "Amounts <= 0",
            "First date", "Last date", "Months in sample",
            "Corridor inconsistent with origin/destination",
            SEGMENT_MISMATCH, MULTI_SEGMENT,
            "Transactions before user registration",
        ],
        "value": [
            len(tx_raw), len(users),
            int(tx_raw.isna().sum().sum()), int(users.isna().sum().sum()),
            int(tx_raw["transaction_id"].duplicated().sum()),
            int(users["user_id"].duplicated().sum()),
            int((~tx_raw["user_id"].isin(users["user_id"])).sum()),
            int((tx_raw["amount_usd"] <= 0).sum()),
            str(df["date"].min().date()), str(df["date"].max().date()),
            df["month"].nunique(),
            int(_corridor_mismatch(tx_raw)),
            round(float((df["user_segment"] != df["user_segment_profile"]).mean()), 4),
            int((tx_raw.groupby("user_id")["user_segment"].nunique() > 1).sum()),
            int((df["tenure_days"] < 0).sum()),
        ],
    }).set_index("check")
    r.add("q_checks", checks)

    r.add("q_amount_stats", df["amount_usd"].describe().rename_axis("metric").to_frame("amount_usd"))
    r.add("q_amount_by_segment",
          df.groupby("user_segment")["amount_usd"].agg(["min", "median", "mean", "max"]))
    r.add("q_categories", pd.concat(
        {c: tx_raw[c].value_counts() for c in cfg.CATEGORICAL_COLUMNS}, names=["column", "value"]
    ).to_frame("count"))

    r.facts.update(
        n_tx=len(tx_raw), n_users=len(users),
        date_min=checks.loc["First date", "value"],
        date_max=checks.loc["Last date", "value"],
        segment_mismatch=checks.loc[SEGMENT_MISMATCH, "value"],
        users_multi_segment=checks.loc[MULTI_SEGMENT, "value"],
    )
    return r


def _corridor_mismatch(tx: pd.DataFrame) -> int:
    code = {"US": "USD", "MX": "MXN", "CO": "COP"}
    expected = tx["source_country"].map(code) + "_" + tx["destination_country"].map(code)
    return (expected != tx["corridor"]).sum()
