"""Number formatting and table presentation (shared by the Markdown report, Excel and Word)."""
from __future__ import annotations


def num(x: float, d: int = 0) -> str:
    return f"{x:,.{d}f}"


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:,.{d}f}%"


def usd(x: float) -> str:
    """Compact: US$126.6M · US$500K · US$950."""
    if abs(x) >= 1e6:
        return f"US${x / 1e6:,.1f}M"
    if abs(x) >= 1e3:
        return f"US${x / 1e3:,.0f}K"
    return f"US${x:,.0f}"


def usd_exact(x: float) -> str:
    """Exact: US$7,271."""
    return f"US${x:,.0f}"


def arrow(corridor: str) -> str:
    return corridor.replace("_", "→")


# --------------------------------------------------------------------------- #
# Table presentation
# --------------------------------------------------------------------------- #
# column -> (display label, kind). Kinds: int, dec1, dec2, dec3, pct, usd, x, text
COLUMNS: dict[str, tuple[str, str]] = {
    # index columns
    "corridor": ("Corridor", "text"), "user_id": ("User", "text"), "country": ("Country", "text"),
    "user_segment": ("Segment", "text"), "user_segment_profile": ("Segment (profile)", "text"),
    "weekday": ("Day", "text"), "hour": ("Hour", "int"), "month": ("Month", "text"),
    "destination_country": ("Destination", "text"), "source_country": ("Origin", "text"),
    "amount_band": ("Amount (USD)", "text"), "near_band": ("SME amount (USD)", "text"),
    "scenario": ("Scenario", "text"), "hypothesis": ("Hypothesis", "text"), "check": ("Check", "text"),
    "user_status": ("User status", "text"), "tx_per_user_bucket": ("Tx per user", "int"),
    "metric": ("Metric", "text"), "index": ("Metric", "text"), "column": ("Column", "text"),
    "count": ("Count", "int"),
    # metrics
    "num_tx": ("Transactions", "int"), "total_usd": ("Value (USD)", "usd"), "success_usd": ("Successful value", "usd"),
    "failed_usd": ("Failed value", "usd"), "success_rate": ("Success rate", "pct"),
    "failure_rate": ("Failure rate", "pct"), "failed_value_rate": ("Failed value %", "pct"),
    "avg_ticket": ("Avg ticket", "usd"), "median_ticket": ("Median ticket", "usd"),
    "users": ("Users", "int"), "active_days": ("Days with data", "int"), "tx_per_day": ("Tx per day", "dec1"),
    "tx_per_user": ("Tx per user", "dec2"), "pct_tx": ("% of tx", "pct"), "pct_usd": ("% of value", "pct"),
    "usd_per_day": ("USD per day", "usd"), "tx_per_day_change": ("MoM change", "pct"),
    "corridor_failure_rate": ("Corridor failure", "pct"), "rest_failure_rate": ("Other corridors", "pct"),
    "corridor_num_tx": ("Corridor tx", "int"), "corridor_failed_tx": ("Corridor failures", "int"),
    "lift_vs_rest": ("Times vs others", "x"), "share_of_failures": ("% of failures", "pct"),
    "chi2": ("Chi²", "dec2"), "p_value": ("p-value", "dec3"), "conclusion": ("Conclusion", "text"),
    "evidence": ("Evidence in the data", "text"), "how_to_validate": ("How to validate", "text"),
    "monthly_value_usd": ("Monthly value", "usd"), "monthly_failed_value_usd": ("Monthly failed value", "usd"),
    "failed_value_share": ("Failed value %", "pct"), "monthly_revenue_lost_usd": ("Revenue lost / month", "usd"),
    "monthly_gain_at_target_usd": ("Gain at 5% / month", "usd"),
    "monthly_gain_at_target_by_count_usd": ("Gain at 5% (count-based)", "usd"),
    "annual_gain_usd": ("Annual gain", "usd"),
    "revenue_month_scaled": ("Monthly revenue (scaled)", "usd"), "growth_q4_vs_q3": ("Growth Q4 vs Q3", "pct"),
    "recoverable_revenue": ("Recoverable / month", "usd"), "market_score": ("Market (1-5)", "int"),
    "simplicity_score": ("Simplicity (1-5)", "int"), "score": ("Score", "dec2"), "rank": ("Rank", "int"),
    "winner": ("Winner", "text"), "value": ("Value", "dec2"), "weight": ("Weight", "pct"),
}

FORMATTERS = {"int": lambda x: num(x), "dec1": lambda x: num(x, 1), "dec2": lambda x: num(x, 2),
              "dec3": lambda x: num(x, 3), "pct": pct, "usd": usd_exact, "x": lambda x: num(x, 1) + "×",
              "text": str}

EXCEL_FORMATS = {"int": "#,##0", "dec1": "#,##0.0", "dec2": "#,##0.00", "dec3": "0.000", "pct": "0.0%",
                 "usd": '"US$"#,##0', "x": '0.0"x"', "text": "@"}


def label(col: str) -> str:
    return COLUMNS.get(col, (col, "text"))[0]


def kind(col: str, sample=None) -> str:
    if col in COLUMNS:
        return COLUMNS[col][1]
    if isinstance(sample, int) and not isinstance(sample, bool):
        return "int"
    if isinstance(sample, float):
        return "dec2"
    return "text"


def cell(value, k: str) -> str:
    """Format one value as text; tolerates mixed-type columns."""
    if value is None or value != value:            # None / NaN
        return ""
    if isinstance(value, str) or k == "text" or not hasattr(value, "__float__"):
        return str(value)
    if float(value).is_integer() and k in ("dec1", "dec2", "dec3"):
        return num(value)
    return FORMATTERS[k](value)
