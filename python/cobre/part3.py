"""Part 3 · Decision matrix to choose the corridor to prioritize in 2026."""
from __future__ import annotations

import pandas as pd

from . import config as cfg
from .data import months_in_sample, scale_factor
from .fmt import label
from .metrics import summarize
from .result import Result


def run(df: pd.DataFrame) -> Result:
    r = Result("p3_strategy")
    months, factor = months_in_sample(df), scale_factor(df)

    s = summarize(df, "corridor")
    q = df.groupby(["corridor", "quarter"]).agg(usd=("amount_usd", "sum"), days=("date", "nunique"))
    usd_day = (q["usd"] / q["days"]).unstack()

    sc = pd.DataFrame(index=s.index)
    sc["num_tx"] = s["num_tx"]
    sc["pct_usd"] = s["pct_usd"]
    sc["revenue_month_scaled"] = s["success_usd"] / months * cfg.FEE_RATE * factor
    sc["growth_q4_vs_q3"] = usd_day["Q4"] / usd_day["Q3"] - 1
    sc["success_rate"] = s["success_rate"]
    sc["recoverable_revenue"] = ((s["failed_value_rate"] - cfg.TARGET_FAILURE_RATE).clip(lower=0)
                                 * s["total_usd"] / months * cfg.FEE_RATE * factor)
    sc["market_score"] = pd.Series(cfg.MARKET_SCORE)
    sc["simplicity_score"] = pd.Series(cfg.SIMPLICITY_SCORE)

    # Min-max normalization of each criterion and weighted score
    norm = pd.DataFrame(index=sc.index)
    for crit in cfg.SCORE_WEIGHTS:
        col = sc[crit]
        rng = col.max() - col.min()
        norm[crit] = (col - col.min()) / rng if rng else 0.0
    sc["score"] = sum(norm[c] * w for c, w in cfg.SCORE_WEIGHTS.items())
    sc["rank"] = sc["score"].rank(ascending=False).astype(int)
    sc = sc.sort_values("rank")
    r.add("p3_scorecard", sc)
    r.add("p3_scorecard_normalized", norm.loc[sc.index])
    r.add("p3_weights", pd.Series(cfg.SCORE_WEIGHTS, name="weight").to_frame())

    # Sensitivity: does the winner change if one criterion is removed?
    sens = {}
    for drop in cfg.SCORE_WEIGHTS:
        w = {k: v for k, v in cfg.SCORE_WEIGHTS.items() if k != drop}
        tot = sum(w.values())
        score = sum(norm[k] * v / tot for k, v in w.items())
        sens[f"Without {label(drop)}"] = score.idxmax()
    r.add("p3_sensitivity", pd.Series(sens, name="winner").rename_axis("scenario").to_frame())

    winner = sc.index[0]
    w = sc.loc[winner]
    r.facts.update(
        winner=winner, runner_up=sc.index[1], scorecard=sc.to_dict("index"),
        robust=all(v == winner for v in sens.values()),
        winner_revenue=w["revenue_month_scaled"], winner_recoverable=w["recoverable_revenue"],
        winner_growth=w["growth_q4_vs_q3"], winner_success=w["success_rate"],
        winner_pct_usd=w["pct_usd"], factor=factor,
    )
    return r
