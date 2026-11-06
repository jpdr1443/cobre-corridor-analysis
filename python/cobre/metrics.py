"""Reusable metrics. Replaces the groupby/agg blocks that were copied into every script."""
from __future__ import annotations

from typing import Iterable

import pandas as pd

_BASE_AGG = dict(
    num_tx=("transaction_id", "count"),
    total_usd=("amount_usd", "sum"),
    success_usd=("success_usd", "sum"),
    failed_usd=("failed_usd", "sum"),
    success_rate=("is_success", "mean"),
    avg_ticket=("amount_usd", "mean"),
    median_ticket=("amount_usd", "median"),
    users=("user_id", "nunique"),
    active_days=("date", "nunique"),
)


def summarize(df: pd.DataFrame, by: str | list[str] | None = None,
              sort_by: str | None = None, ascending: bool = False) -> pd.DataFrame:
    """Standard KPIs for any grouping (or for the whole df when by=None).

    Columns: num_tx, total_usd, success_usd, failed_usd, success_rate,
    failure_rate, failed_value_rate, avg_ticket, median_ticket, users,
    active_days, tx_per_day, pct_tx, pct_usd.
    """
    if by is None:
        out = df.assign(_all="Total").groupby("_all").agg(**_BASE_AGG)
        out.index.name = None
    else:
        out = df.groupby(by, observed=True).agg(**_BASE_AGG)

    out["failure_rate"] = 1 - out["success_rate"]
    out["failed_value_rate"] = out["failed_usd"] / out["total_usd"]
    out["tx_per_day"] = out["num_tx"] / out["active_days"]
    out["tx_per_user"] = out["num_tx"] / out["users"]
    out["pct_tx"] = out["num_tx"] / len(df)
    out["pct_usd"] = out["total_usd"] / df["amount_usd"].sum()
    if sort_by:
        out = out.sort_values(sort_by, ascending=ascending)
    return out


def share(df: pd.DataFrame, rows: str, cols: str) -> pd.DataFrame:
    """Percentage mix of `cols` within each `rows` value (each row sums to 100%)."""
    return pd.crosstab(df[rows], df[cols], normalize="index")


def rate_matrix(df: pd.DataFrame, rows: str, cols: str,
                value: str = "is_failed") -> pd.DataFrame:
    """Average rate of `value` across two dimensions."""
    return df.pivot_table(index=rows, columns=cols, values=value,
                          aggfunc="mean", observed=True)


def count_matrix(df: pd.DataFrame, rows: str, cols: str) -> pd.DataFrame:
    return df.pivot_table(index=rows, columns=cols, values="transaction_id",
                          aggfunc="count", observed=True)


def segment_vs_rest(df: pd.DataFrame, mask: pd.Series, by: str,
                    labels: tuple[str, str] = ("focus", "rest")) -> pd.DataFrame:
    """Failure rate of a subset vs the rest, broken down by `by`."""
    focus, rest = labels
    a = df[mask].groupby(by, observed=True)["is_failed"].agg(["mean", "size", "sum"])
    b = df[~mask].groupby(by, observed=True)["is_failed"].mean()
    out = pd.DataFrame({
        f"{focus}_failure_rate": a["mean"],
        f"{focus}_num_tx": a["size"],
        f"{focus}_failed_tx": a["sum"],
        f"{rest}_failure_rate": b,
    })
    out["lift_vs_rest"] = out[f"{focus}_failure_rate"] / out[f"{rest}_failure_rate"]
    out["share_of_failures"] = out[f"{focus}_failed_tx"] / out[f"{focus}_failed_tx"].sum()
    return out


def spread(series: pd.Series) -> float:
    """Max minus min (in points of the same unit)."""
    return float(series.max() - series.min())


def ordered(df: pd.DataFrame, order: Iterable) -> pd.DataFrame:
    """Reorder the index following a list, ignoring missing values."""
    return df.reindex([o for o in order if o in df.index])
