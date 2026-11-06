"""Part 2 · Root cause of the problem corridor's failures and revenue impact."""
from __future__ import annotations

import math

import pandas as pd

from . import config as cfg
from .data import months_in_sample, scale_factor
from .fmt import pct
from .metrics import count_matrix, rate_matrix, segment_vs_rest, spread
from .result import Result

FOCUS, REST = "corridor", "rest"
REST_LABEL = "Other corridors"
SAMPLE, SCALED, BRIEF = "Sample (data as is)", "Scaled to US$1.5B/month", "Brief scenario (35%, 15%)"


def run(df: pd.DataFrame, corridor: str = cfg.PROBLEM_CORRIDOR) -> Result:
    r = Result("p2_root_cause")
    mask = df["corridor"] == corridor
    c = df[mask]

    # --- Overview --------------------------------------------------------------
    overview = pd.DataFrame({
        "failure_rate": [c["is_failed"].mean(), df.loc[~mask, "is_failed"].mean(), df["is_failed"].mean()],
        "failed_value_rate": [c["failed_usd"].sum() / c["amount_usd"].sum(),
                              df.loc[~mask, "failed_usd"].sum() / df.loc[~mask, "amount_usd"].sum(),
                              df["failed_usd"].sum() / df["amount_usd"].sum()],
        "num_tx": [len(c), int((~mask).sum()), len(df)],
        "failed_tx": [int(c["is_failed"].sum()), int(df.loc[~mask, "is_failed"].sum()), int(df["is_failed"].sum())],
    }, index=[corridor, REST_LABEL, "Total"])
    r.add("p2_overview", overview)
    share_of_all_failures = c["is_failed"].sum() / df["is_failed"].sum()

    # --- Cuts: corridor vs rest (same function for every dimension) -----------
    cuts = {
        "p2_by_segment": "user_segment",
        "p2_by_amount_band": "amount_band",
        "p2_by_weekday": "weekday",
        "p2_by_hour": "hour",
        "p2_by_month": "month",
        "p2_by_user_country": "country",
        "p2_by_user_status": "user_status",
    }
    for key, col in cuts.items():
        r.add(key, segment_vs_rest(df, mask, col, labels=(FOCUS, REST)))
    r.tables["p2_by_weekday"] = r.tables["p2_by_weekday"].reindex(cfg.WEEKDAYS.values())

    # Segment × amount (within the corridor): separates both effects
    r.add("p2_segment_x_band_failure", rate_matrix(c, "user_segment", "amount_band"))
    r.add("p2_segment_x_band_count", count_matrix(c, "user_segment", "amount_band"))

    # --- 10K threshold test within SME (the only segment that crosses it) -----
    bins = [0, 8_000, 9_000, 9_500, 10_000, 10_500]
    labels = ["<=8k", "8k-9k", "9k-9.5k", "9.5k-10k", "10k-10.5k"]
    sme = df[df["user_segment"] == "sme"].assign(
        near_band=lambda d: pd.cut(d["amount_usd"], bins, labels=labels))
    threshold = segment_vs_rest(sme, sme["corridor"] == corridor, "near_band", labels=(FOCUS, REST))
    r.add("p2_threshold_sme", threshold)
    sme_c = sme[sme["corridor"] == corridor]
    below = sme_c.loc[sme_c["amount_usd"] <= cfg.THRESHOLD_USD, "is_failed"].mean()
    above = sme_c.loc[sme_c["amount_usd"] > cfg.THRESHOLD_USD, "is_failed"].mean()

    # --- Does the day matter? Chi-square test of independence -----------------
    wd_chi2, wd_p = _chi2(c, "weekday")
    seg_chi2, seg_p = _chi2(c, "user_segment")
    daily = c.groupby("date")["is_failed"].mean()
    r.add("p2_daily_failure_stats", daily.describe().to_frame("daily_failure_rate"))
    r.add("p2_significance", pd.DataFrame({
        "chi2": [seg_chi2, wd_chi2], "p_value": [seg_p, wd_p],
        "conclusion": [_verdict(seg_p), _verdict(wd_p)],
    }, index=["user_segment", "weekday"]))

    # --- Concentration by user -------------------------------------------------
    fails_by_user = c.loc[c["is_failed"] == 1, "user_id"].value_counts()
    r.add("p2_user_concentration", pd.Series({
        "Users with failures": fails_by_user.size,
        "Users in the corridor": c["user_id"].nunique(),
        "Share of failures from top 10 users": fails_by_user.head(10).sum() / fails_by_user.sum(),
        "Max failures for one user": int(fails_by_user.max()),
    }).rename_axis("metric").to_frame("value"))

    # --- Revenue impact -----------------------------------------------------------
    impact = _impact(df, c)
    r.add("p2_impact", impact)

    # --- Hypotheses (text fed by the numbers) -----------------------------------
    seg = r.tables["p2_by_segment"]
    band = r.tables["p2_by_amount_band"]
    wd = r.tables["p2_by_weekday"]
    r.add("p2_hypotheses", _hypotheses(seg, band, below, above))

    r.facts.update(
        corridor=corridor,
        failure_rate=overview.loc[corridor, "failure_rate"],
        rest_failure=overview.loc[REST_LABEL, "failure_rate"],
        failed_value_rate=overview.loc[corridor, "failed_value_rate"],
        lift=overview.loc[corridor, "failure_rate"] / overview.loc[REST_LABEL, "failure_rate"],
        share_of_all_failures=share_of_all_failures,
        seg_rates=seg["corridor_failure_rate"].to_dict(),
        seg_share=seg["share_of_failures"].to_dict(),
        band_rates=band["corridor_failure_rate"].to_dict(),
        over10k_rate=band.loc[">10k", "corridor_failure_rate"],
        wd_rates=wd["corridor_failure_rate"].to_dict(),
        wd_min=wd["corridor_failure_rate"].min(), wd_max=wd["corridor_failure_rate"].max(),
        friday_rate=wd.loc["Friday", "corridor_failure_rate"], wd_p=wd_p, seg_p=seg_p,
        month_spread=spread(r.tables["p2_by_month"]["corridor_failure_rate"]),
        hour_spread=spread(r.tables["p2_by_hour"]["corridor_failure_rate"]),
        sme_below=below, sme_above=above,
        rest_seg_max=seg["rest_failure_rate"].max(),
        top10_user_share=fails_by_user.head(10).sum() / fails_by_user.sum(),
        users_with_fails=fails_by_user.size,
        impact=impact.to_dict("index"),
    )
    return r


# --------------------------------------------------------------------------- #
def _impact(df: pd.DataFrame, c: pd.DataFrame) -> pd.DataFrame:
    months = months_in_sample(df)
    factor = scale_factor(df)
    fee, target = cfg.FEE_RATE, cfg.TARGET_FAILURE_RATE

    value_m = c["amount_usd"].sum() / months
    failed_m = c["failed_usd"].sum() / months
    fvr = failed_m / value_m
    lost = failed_m * fee
    gain = max(fvr - target, 0) * value_m * fee

    # Count-based alternative (failure by # of tx × average ticket)
    fr = c["is_failed"].mean()
    gain_count = max(fr - target, 0) * len(c) / months * c["amount_usd"].mean() * fee

    # Literal brief scenario: 35% of volume, 15% failure
    brief_value = cfg.COBRE_MONTHLY_VOLUME_USD * 0.35

    rows = {
        SAMPLE: [value_m, failed_m, fvr, lost, gain, gain_count],
        SCALED: [value_m * factor, failed_m * factor, fvr, lost * factor,
                                       gain * factor, gain_count * factor],
        BRIEF: [brief_value, brief_value * 0.15, 0.15,
                                                  brief_value * 0.15 * fee,
                                                  brief_value * (0.15 - target) * fee,
                                                  brief_value * (0.15 - target) * fee],
    }
    out = pd.DataFrame(rows, index=["monthly_value_usd", "monthly_failed_value_usd",
                                    "failed_value_share", "monthly_revenue_lost_usd",
                                    "monthly_gain_at_target_usd",
                                    "monthly_gain_at_target_by_count_usd"]).T
    out.index.name = "scenario"
    out["annual_gain_usd"] = out["monthly_gain_at_target_usd"] * 12
    out.attrs["scale_factor"] = factor
    return out


def _chi2(df: pd.DataFrame, col: str) -> tuple[float, float]:
    obs = pd.crosstab(df[col], df["is_failed"]).to_numpy(dtype=float)
    exp = obs.sum(1, keepdims=True) * obs.sum(0, keepdims=True) / obs.sum()
    chi2 = float(((obs - exp) ** 2 / exp).sum())
    dof = (obs.shape[0] - 1) * (obs.shape[1] - 1)
    return chi2, _chi2_sf(chi2, dof)


def _chi2_sf(x: float, k: int) -> float:
    """P(X > x) for chi² with k d.o.f. (regularized incomplete gamma; no scipy needed)."""
    a, z = k / 2.0, x / 2.0
    if z <= 0:
        return 1.0
    if z < a + 1:                                    # series for P(a, z)
        term = total = 1.0 / a
        n = a
        for _ in range(500):
            n += 1
            term *= z / n
            total += term
            if term < total * 1e-15:
                break
        return 1.0 - total * math.exp(-z + a * math.log(z) - math.lgamma(a))
    b, c, d = z + 1 - a, 1e300, 1 / (z + 1 - a)     # continued fraction for Q(a, z)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = b + an / c
        c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return math.exp(-z + a * math.log(z) - math.lgamma(a)) * h


def _verdict(p: float) -> str:
    return "Significant difference (p<0.05)" if p < 0.05 else "Not significant: random noise"


def _hypotheses(seg: pd.DataFrame, band: pd.DataFrame, below: float, above: float) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "hypothesis": "H1 · Compliance (AML) rule or payout-bank limit on payments > US$10K",
            "evidence": (f">10K fails {pct(band.loc['>10k', 'corridor_failure_rate'])}; within SME the rate jumps "
                         f"from {pct(below)} (≤10K) to {pct(above)} (>10K). In other corridors >10K fails "
                         f"{pct(band.loc['>10k', 'rest_failure_rate'])}, the same as any amount."),
            "how_to_validate": "Cross-check rejection/error codes from the MXN provider; review SPEI and payout-bank "
                               "limits and screening rules; A/B test splitting or pre-approval.",
        },
        {
            "hypothesis": "H2 · Invalid beneficiary/KYC data in retail (CLABE, name)",
            "evidence": (f"Retail fails {pct(seg.loc['retail', 'corridor_failure_rate'])} and accounts for "
                         f"{pct(seg.loc['retail', 'share_of_failures'])} of failures, with tickets < US$4.2K."),
            "how_to_validate": "Distribution of rejection reasons by segment; retry success rate after fixing "
                               "data; validate CLABE at checkout and measure before/after.",
        },
        {
            "hypothesis": "H3 · Structural issue with the USD→MXN provider or settlement route",
            "evidence": ("Every segment, hour, day and month fails ~3-4× more than in other corridors: the issue "
                         "belongs to the corridor, not to the customer or the calendar."),
            "how_to_validate": "Compare failure rate by provider/payout bank and by outage timestamp; SLA and "
                               "timeout logs; route a share of volume through an alternative provider.",
        },
    ]).set_index("hypothesis")
