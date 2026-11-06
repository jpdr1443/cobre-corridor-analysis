"""Data loading and enrichment (done once for the whole project)."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from . import config as cfg


def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the original CSV files unchanged."""
    tx = pd.read_csv(cfg.TRANSACTIONS_FILE)
    users = pd.read_csv(cfg.USERS_FILE)
    return tx, users


def enrich(tx: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    """Add helper columns and the user profile to every transaction."""
    df = tx.copy()

    # Status
    df["is_success"] = (df["status"] == cfg.SUCCESS).astype(int)
    df["is_failed"] = 1 - df["is_success"]
    df["success_usd"] = df["amount_usd"] * df["is_success"]
    df["failed_usd"] = df["amount_usd"] * df["is_failed"]

    # Time
    df["datetime"] = pd.to_datetime(df["transaction_date"] + " " + df["transaction_time"])
    df["date"] = df["datetime"].dt.normalize()
    df["hour"] = df["datetime"].dt.hour
    df["weekday_n"] = df["datetime"].dt.dayofweek
    df["weekday"] = df["weekday_n"].map(cfg.WEEKDAYS)
    df["month"] = df["datetime"].dt.to_period("M").astype(str)
    df["quarter"] = "Q" + df["datetime"].dt.quarter.astype(str)

    # Amount
    df["amount_band"] = pd.cut(df["amount_usd"], bins=cfg.AMOUNT_BINS,
                               labels=cfg.AMOUNT_LABELS, right=True)
    df["over_threshold"] = (df["amount_usd"] > cfg.THRESHOLD_USD).astype(int)

    # User profile (suffix _profile so it does not overwrite the transaction segment)
    profile = users.rename(columns={"user_segment": "user_segment_profile",
                                    "status": "user_status"})
    df = df.merge(profile, on="user_id", how="left", validate="many_to_one")
    df["registration_date"] = pd.to_datetime(df["registration_date"])
    df["tenure_days"] = (df["date"] - df["registration_date"]).dt.days
    return df


@lru_cache(maxsize=1)
def get_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Single entry point: returns (enriched transactions, users)."""
    tx, users = load_raw()
    return enrich(tx, users), users


def months_in_sample(df: pd.DataFrame) -> int:
    return df["month"].nunique()


def scale_factor(df: pd.DataFrame) -> float:
    """Factor that scales the sample to Cobre's real monthly volume."""
    sample_monthly = df["amount_usd"].sum() / months_in_sample(df)
    return cfg.COBRE_MONTHLY_VOLUME_USD / sample_monthly
