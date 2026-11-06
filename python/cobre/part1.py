"""Part 1 · Data analysis: corridors, users and time patterns.

Replaces the original primerAnalisisParte1/2/2_2/3 scripts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .metrics import count_matrix, rate_matrix, share, spread, summarize
from .result import Result


# --------------------------------------------------------------------------- #
# 1.1 Corridors
# --------------------------------------------------------------------------- #
def corridors(df: pd.DataFrame) -> Result:
    r = Result("p1_corridors")
    s = r.add("p1_corridor_summary", summarize(df, "corridor", sort_by="num_tx"))

    r.add("p1_top5_volume", s.nlargest(5, "num_tx")[["num_tx", "pct_tx"]])
    r.add("p1_top5_value", s.nlargest(5, "total_usd")[["total_usd", "success_usd", "pct_usd"]])
    r.add("p1_success_rank", s.sort_values("success_rate", ascending=False)[["success_rate", "failure_rate"]])
    r.add("p1_ticket", s.sort_values("avg_ticket", ascending=False)[["avg_ticket", "median_ticket"]])
    r.add("p1_corridor_segment_mix", share(df, "corridor", "user_segment"))

    total = summarize(df).iloc[0]
    rest = df[df["corridor"] != cfg.PROBLEM_CORRIDOR]["is_failed"].mean()
    r.facts.update(
        total_usd=total["total_usd"], overall_success=total["success_rate"],
        overall_failure=total["failure_rate"], rest_failure=rest,
        top_volume=s.index[0], corridor=s.to_dict("index"),
        best_success=s["success_rate"].idxmax(), worst_success=s["success_rate"].idxmin(),
    )
    return r


# --------------------------------------------------------------------------- #
# 1.2 Users
# --------------------------------------------------------------------------- #
def users(df: pd.DataFrame, users_df: pd.DataFrame) -> Result:
    r = Result("p1_users")

    per_user = df.groupby("user_id").size()
    stats = pd.Series({
        "Registered users": len(users_df),
        "Users with at least 1 tx": per_user.size,
        "Avg tx per active user": per_user.mean(),
        "Avg tx per registered user": len(df) / len(users_df),
        "Median": per_user.median(),
        "P90": per_user.quantile(0.9),
        "Min": per_user.min(),
        "Max": per_user.max(),
    }).rename_axis("metric").to_frame("value")
    r.add("p1_tx_per_user_stats", stats)
    r.add("p1_tx_per_user_distribution",
          per_user.value_counts().sort_index().rename("users").rename_axis("tx_per_user_bucket").to_frame())

    top = summarize(df, ["user_id", "country", "user_segment_profile"])
    top = top.sort_values(["num_tx", "total_usd"], ascending=False).head(10)
    r.add("p1_top10_users", top[["num_tx", "total_usd", "avg_ticket", "success_rate"]])

    # Mexico vs Colombia by user country
    by_country = r.add("p1_country_comparison", summarize(df, "country"))
    r.add("p1_country_segment_mix", share(df, "country", "user_segment_profile"))
    r.add("p1_country_corridor_mix", share(df, "country", "corridor"))

    # Money flows: what arrives in / leaves each country
    inbound = summarize(df[df["destination_country"].isin(["MX", "CO"])], "destination_country")
    outbound = summarize(df[df["source_country"].isin(["MX", "CO"])], "source_country")
    r.add("p1_mx_co_inbound", inbound)
    r.add("p1_mx_co_outbound", outbound)

    r.facts.update(
        avg_tx_active=per_user.mean(), avg_tx_registered=len(df) / len(users_df),
        median_tx=per_user.median(), max_tx=int(per_user.max()),
        active_users=per_user.size, top_user=top.index[0][0], top_user_tx=int(top.iloc[0]["num_tx"]),
        country=by_country.to_dict("index"),
        inbound=inbound.to_dict("index"), outbound=outbound.to_dict("index"),
    )
    return r


# --------------------------------------------------------------------------- #
# 1.3 Time
# --------------------------------------------------------------------------- #
def time_patterns(df: pd.DataFrame) -> Result:
    r = Result("p1_time")

    wd = summarize(df, ["weekday_n", "weekday"]).droplevel(0)
    r.add("p1_weekday", wd[["num_tx", "total_usd", "active_days", "tx_per_day", "success_rate"]])

    hr = summarize(df, "hour")
    r.add("p1_hour", hr[["num_tx", "total_usd", "pct_tx", "success_rate"]])

    heat = count_matrix(df, "hour", "weekday_n").rename(columns=cfg.WEEKDAYS)
    r.add("p1_heatmap_hour_weekday", heat)

    mo = summarize(df, "month")
    mo["tx_per_day_change"] = mo["tx_per_day"].pct_change()
    mo["usd_per_day"] = mo["total_usd"] / mo["active_days"]
    r.add("p1_month", mo[["num_tx", "total_usd", "active_days", "tx_per_day",
                          "usd_per_day", "tx_per_day_change", "success_rate"]])

    r.add("p1_month_corridor_tx", count_matrix(df, "month", "corridor"))
    r.add("p1_month_corridor_failure", rate_matrix(df, "month", "corridor"))

    daily = df.groupby("date").size()
    slope = np.polyfit(np.arange(len(daily)), daily.values, 1)[0]     # tx/day per day
    r.add("p1_daily", daily.rename("num_tx").to_frame())

    first, last = mo["tx_per_day"].iloc[0], mo["tx_per_day"].iloc[-1]
    r.facts.update(
        top_weekday=wd["tx_per_day"].idxmax(), low_weekday=wd["tx_per_day"].idxmin(),
        weekday_spread_pct=spread(wd["tx_per_day"]) / wd["tx_per_day"].mean(),
        hour_min=int(hr.index.min()), hour_max=int(hr.index.max()),
        peak_hour=int(hr["num_tx"].idxmax()),
        hour_spread_pct=spread(hr["num_tx"]) / hr["num_tx"].mean(),
        tx_per_day_first=first, tx_per_day_last=last,
        tx_per_day_avg=daily.mean(), change_first_last=last / first - 1,
        trend_slope_per_month=slope * 30, trend_slope_pct=slope * 30 / daily.mean(),
    )
    return r


def run(df: pd.DataFrame, users_df: pd.DataFrame) -> list[Result]:
    return [corridors(df), users(df, users_df), time_patterns(df)]
