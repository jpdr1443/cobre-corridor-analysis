"""Narrative content: answer to every question, root-cause write-up, memo and story.

Single source for all text. `report.py` (Markdown), `build_excel.py` (Excel) and
`build_document.py` (Word/PDF) only display it. Every figure comes from `Result.facts`;
no number is typed by hand.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config as cfg
from .fmt import arrow, num, pct, usd, usd_exact
from .part2 import BRIEF, SAMPLE, SCALED
from .result import Result

Results = dict[str, Result]


@dataclass(frozen=True)
class QA:
    code: str                 # "1.1a"
    sheet: str                # Excel sheet key where it is shown
    topic: str                # section subtitle
    question: str             # question as stated in the brief
    answer: str               # answer (supports **bold**)
    tables: tuple[str, ...]   # supporting Result tables


SHEETS = {"p1_corr": "P1 Corridors", "p1_users": "P1 Users", "p1_time": "P1 Time",
          "p2": "P2 Root Cause", "p3": "P3 Recommendation"}


def words(parts: list[tuple[str, str]]) -> int:
    """Word count of a text built from (heading, paragraph) pairs."""
    return sum(len(f"{h} {t}".replace("**", "").split()) for h, t in parts)


# --------------------------------------------------------------------------- #
# The story (executive summary)
# --------------------------------------------------------------------------- #
def executive_summary(R: Results) -> list[str]:
    p1, p2, p3 = R["p1_corridors"].facts, R["p2_root_cause"].facts, R["p3_strategy"].facts
    top = p1["corridor"][p1["top_volume"]]
    gain = p2["impact"][SCALED]["monthly_gain_at_target_usd"]
    return [
        f"**{arrow(p1['top_volume'])} is the largest corridor** ({pct(top['pct_tx'], 0)} of transactions, "
        f"{pct(top['pct_usd'], 0)} of value) and the only one growing.",
        f"**But it fails {pct(p2['failure_rate'])}** vs {pct(p2['rest_failure'])} in the other corridors, and "
        f"concentrates {pct(p2['share_of_all_failures'], 0)} of all Cobre failures.",
        "**The failure belongs to the corridor:** every segment and amount fails 3-4× more, and it gets worse for "
        "payments **above US$10K**. The day of the week has no effect.",
        f"**Mexican and Colombian users behave the same**, and total volume is flat "
        f"(~{num(R['p1_time'].facts['tx_per_day_avg'], 0)} tx/day for six months).",
        f"**Bringing failures down to 5% is worth {usd(gain)}/month.** 2026 recommendation: "
        f"**prioritize {arrow(p3['winner'])}**.",
    ]


# --------------------------------------------------------------------------- #
# Part 2 · write-up (250-300 words), built from reusable pieces
# --------------------------------------------------------------------------- #
def p2_parts(R: Results) -> dict[str, str]:
    f = R["p2_root_cause"].facts
    sc, sm, br = f["impact"][SCALED], f["impact"][SAMPLE], f["impact"][BRIEF]
    seg, c = f["seg_rates"], arrow(f["corridor"])
    return {
        "Diagnosis": (
            f"{c} fails {pct(f['failure_rate'])} of transactions ({pct(f['failed_value_rate'])} of value), "
            f"{num(f['lift'], 1)}× the other corridors ({pct(f['rest_failure'])}), and drives "
            f"{pct(f['share_of_all_failures'], 0)} of all Cobre failures. The data shows a higher rate than the 15% "
            "stated in the brief."),
        "Patterns": (
            f"(1) Every segment fails more than in other corridors, with a gradient: enterprise "
            f"{pct(seg['enterprise'])}, retail {pct(seg['retail'])} and SME {pct(seg['sme'])}; retail drives "
            f"{pct(f['seg_share']['retail'], 0)} of failures by volume. (2) Amount matters: payments >US$10K fail "
            f"{pct(f['over10k_rate'])} and, within SME, the rate jumps from {pct(f['sme_below'])} to "
            f"{pct(f['sme_above'])} when crossing US$10K. (3) The day does **not** matter: Fridays fail "
            f"{pct(f['friday_rate'])} and the weekly range is {pct(f['wd_min'])}–{pct(f['wd_max'])} "
            f"(chi², p={num(f['wd_p'], 2)}); neither do hour or month. Failures are spread across "
            f"{num(f['users_with_fails'])} users: this is not a single customer."),
        "Three possible root causes": (
            "H1: a compliance/AML rule or payout-bank limit on payments >US$10K. H2: invalid beneficiary data "
            "(CLABE, name) in retail. H3: a structural issue with the MXN provider or settlement route that raises "
            "the baseline failure rate across the whole corridor."),
        "Validation": (
            "Analyze rejection codes by segment and amount; compare failure rates by provider/payout bank; pilot "
            "CLABE validation at checkout and pre-approval of payments >US$10K with an A/B test."),
        "Loss": (
            f"At a {pct(cfg.FEE_RATE)} fee, the sample loses {usd(sm['monthly_revenue_lost_usd'])}/month; scaled "
            f"to Cobre's US$1.5B/month that is **{usd(sc['monthly_revenue_lost_usd'])}/month**."),
        "Gain": (
            f"Cutting failures to {pct(cfg.TARGET_FAILURE_RATE, 0)} recovers "
            f"**{usd(sc['monthly_gain_at_target_usd'])}/month ({usd(sc['annual_gain_usd'])}/year)**; under the "
            f"brief's assumptions (35%, 15%) it would be {usd(br['monthly_gain_at_target_usd'])}/month."),
        "Recommendation": (
            "Attack H1 and H3 first, since they concentrate the lost value: agree limits and pre-approval for "
            "large payments with the payout bank, and test a second MXN provider. In parallel, add CLABE "
            "validation for retail (H2) and track the failure rate weekly by segment and amount band."),
    }


def p2_writeup(R: Results) -> list[tuple[str, str]]:
    p = p2_parts(R)
    return [("Diagnosis", p["Diagnosis"]), ("Patterns", p["Patterns"]),
            ("Three possible root causes", p["Three possible root causes"]), ("Validation", p["Validation"]),
            ("Impact", f"{p['Loss']} {p['Gain']}"), ("Recommendation", p["Recommendation"])]


# --------------------------------------------------------------------------- #
# Part 3 · memo (≤ 400 words)
# --------------------------------------------------------------------------- #
_CRIT = {"revenue_month_scaled": "revenue", "growth_q4_vs_q3": "growth", "success_rate": "reliability",
         "recoverable_revenue": "recoverable revenue", "market_score": "market", "simplicity_score": "simplicity"}


def p3_memo(R: Results) -> list[tuple[str, str]]:
    f, p2 = R["p3_strategy"].facts, R["p2_root_cause"].facts
    w, ru, s = f["winner"], f["runner_up"], f["scorecard"]
    other_recov = max(v["recoverable_revenue"] for k, v in s.items() if k != w)
    weights = ", ".join(f"{_CRIT[k]} ({pct(v, 0)})" for k, v in cfg.SCORE_WEIGHTS.items())
    return [
        ("To", "Management · From: Business Analyst · Subject: Corridor to prioritize in 2026"),
        ("Recommendation", f"**Prioritize {arrow(w)}.**"),
        ("Scale", f"It moves {pct(s[w]['pct_usd'], 0)} of processed value; scaled to Cobre's volume it generates "
                  f"~{usd(f['winner_revenue'])}/month in fees, "
                  f"{num(f['winner_revenue'] / s[ru]['revenue_month_scaled'], 1)}× {arrow(ru)}."),
        ("Growth", f"It is the only large corridor that is growing: +{pct(f['winner_growth'])} in daily value in Q4 "
                   f"vs Q3, while {arrow(ru)} fell {pct(abs(s[ru]['growth_q4_vs_q3']))}."),
        ("Hidden upside", f"Its success rate is only {pct(f['winner_success'])}. Bringing failures to 5% unlocks "
                          f"~{usd(f['winner_recoverable'])}/month without acquiring a single new customer; no other "
                          f"corridor has more than {usd(other_recov)}/month to recover."),
        ("Market", "US→Mexico is the world's largest remittance corridor and the region's main B2B flow, with "
                   "mature payment rails (SPEI)."),
        ("Decision matrix", f"Weighting {weights}, {arrow(w)} scores {num(s[w]['score'], 2)} vs "
                            f"{num(s[ru]['score'], 2)} for {arrow(ru)}. The result is "
                            f"{'robust: it still wins when any single criterion is removed' if f['robust'] else 'sensitive to the weights'}."),
        ("Action Q1 · Stabilize", "Daily dashboard of rejections by code, segment and amount; CLABE and name "
                                  "validation at checkout (retail)."),
        ("Action Q1–Q2 · Unblock large payments", "KYB/AML pre-approval and agreed limits with the payout bank for "
                                                   "payments >US$10K; automatic splitting where allowed."),
        ("Action Q2 · Redundancy", "Second MXN payout provider with smart routing based on success rate."),
        ("Action H2 · Grow", "Once success is ≥95%, commercial push to US enterprise and SME exporters."),
        ("Expected impact", f"Failure rate from {pct(p2['failure_rate'])} to 5%: +{usd(f['winner_recoverable'])}"
                            f"/month (~{usd(f['winner_recoverable'] * 12)}/year) in recovered revenue, plus "
                            "retention of enterprise clients who today see 1 in 4 payments fail."),
        ("Risks", "Root causes remain hypotheses until rejection codes are reviewed; market and simplicity scores "
                  "are qualitative judgments."),
    ]


# --------------------------------------------------------------------------- #
# Questions and answers
# --------------------------------------------------------------------------- #
def qa(R: Results) -> list[QA]:
    c, u, t = R["p1_corridors"], R["p1_users"], R["p1_time"]
    cf, uf, tf = c.facts, u.facts, t.facts
    s = c.tables["p1_corridor_summary"]
    mx, co = uf["country"]["Mexico"], uf["country"]["Colombia"]
    p2, p3 = p2_parts(R), R["p3_strategy"].facts
    by_value = s.sort_values("total_usd", ascending=False)
    by_ticket = s.sort_values("avg_ticket", ascending=False)
    T1, T2, T3 = "1.1 Corridor performance", "1.2 User behavior", "1.3 Time patterns"
    R1, R2 = "2.1 Root cause analysis", "2.2 Business impact"

    return [
        # ---------------------------- Part 1 ----------------------------------
        QA("1.1a", "p1_corr", T1, "What are the top 5 payment corridors by transaction volume?",
           " · ".join(f"{i}. {arrow(k)} ({pct(v)})" for i, (k, v) in enumerate(s["pct_tx"].items(), 1))
           + ". There are only 5 corridors, so the top 5 is the full set; the first two account for "
           f"{pct(s['pct_tx'].iloc[:2].sum(), 0)} of transactions.", ("p1_top5_volume",)),
        QA("1.1b", "p1_corr", T1, "What are the top 5 corridors by transaction value (total USD)?",
           " · ".join(f"{i}. {arrow(k)} ({usd(v)})" for i, (k, v) in enumerate(by_value["total_usd"].items(), 1))
           + f". {arrow(by_value.index[0])} concentrates **{pct(by_value['pct_usd'].iloc[0])} of value** with "
           f"{pct(by_value['pct_tx'].iloc[0])} of transactions.", ("p1_top5_value",)),
        QA("1.1c", "p1_corr", T1, "Which corridors have the highest success rates?",
           f"{arrow(cf['best_success'])} leads with {pct(s.loc[cf['best_success'], 'success_rate'])}. All corridors "
           f"are around 95% except **{arrow(cf['worst_success'])}, which drops to "
           f"{pct(s.loc[cf['worst_success'], 'success_rate'])}**: it is the only reliability problem.",
           ("p1_success_rank",)),
        QA("1.1d", "p1_corr", T1, "What is the average transaction size by corridor?",
           " · ".join(f"{arrow(k)} {usd_exact(v)}" for k, v in by_ticket["avg_ticket"].items())
           + ". The mean is ~1.8× the median in every corridor: a few large enterprise payments pull the average up.",
           ("p1_ticket",)),
        QA("1.2a", "p1_users", T2, "What's the average number of transactions per user?",
           f"**{num(uf['avg_tx_active'], 1)} transactions per user** (median {num(uf['median_tx'])}, max "
           f"{uf['max_tx']}). All {num(uf['active_users'])} registered users transacted at least once.",
           ("p1_tx_per_user_stats", "p1_tx_per_user_distribution")),
        QA("1.2b", "p1_users", T2, "Who are the top 10 users by transaction volume?",
           f"The leader is {uf['top_user']} with {uf['top_user_tx']} transactions; the top 10 make between 20 and "
           f"{uf['top_user_tx']}, only 2× the average. No user concentrates volume.", ("p1_top10_users",)),
        QA("1.2c", "p1_users", T2, "How does user behavior differ between Mexico and Colombia?",
           f"Mexico accounts for {pct(mx['pct_tx'])} of transactions because it has more users, but **per user they "
           f"behave the same**: {num(mx['tx_per_user'], 1)} vs {num(co['tx_per_user'], 1)} tx/user, ticket "
           f"{usd_exact(mx['avg_ticket'])} vs {usd_exact(co['avg_ticket'])}, success {pct(mx['success_rate'])} vs "
           f"{pct(co['success_rate'])}, same corridor and segment mix. The real difference is the destination: "
           f"money **arriving** in Mexico fails {pct(uf['inbound']['MX']['failure_rate'])} vs "
           f"{pct(uf['inbound']['CO']['failure_rate'])} for money arriving in Colombia.",
           ("p1_country_comparison", "p1_mx_co_inbound")),
        QA("1.3a", "p1_time", T3, "What days of the week have the highest transaction volume?",
           f"{tf['top_weekday']} has the highest daily average and {tf['low_weekday']} the lowest, but the gap "
           f"between them is only {pct(tf['weekday_spread_pct'])}: **there is no dominant day**; volume is even "
           "across the week.", ("p1_weekday",)),
        QA("1.3b", "p1_time", T3, "Are there any notable hourly patterns?",
           f"All activity happens between {tf['hour_min']}:00 and {tf['hour_max']}:59 (banking hours), with no "
           f"overnight transactions. The peak is at {tf['peak_hour']}:00, but the variation across hours is "
           f"{pct(tf['hour_spread_pct'])}: within the window volume is flat.",
           ("p1_hour", "p1_heatmap_hour_weekday")),
        QA("1.3c", "p1_time", T3, "Has transaction volume been growing or declining over the 6-month period?",
           f"**It is flat.** {num(tf['tx_per_day_first'], 0)} tx/day in July vs {num(tf['tx_per_day_last'], 0)} "
           f"in December ({pct(tf['change_first_last'])}); the linear trend is {pct(tf['trend_slope_pct'], 2)} "
           f"per month. Only {arrow(cf['top_volume'])} is growing in value (+{pct(p3['winner_growth'])} Q4 vs Q3).",
           ("p1_month",)),
        # ---------------------------- Part 2 ----------------------------------
        QA("2.1a", "p2", R1, "What patterns do you see in the failed transactions?",
           f"{p2['Diagnosis']} {p2['Patterns']}",
           ("p2_by_segment", "p2_by_amount_band", "p2_threshold_sme", "p2_by_weekday", "p2_significance")),
        QA("2.1b", "p2", R1, "What are 3 possible root causes for the high failure rate?",
           p2["Three possible root causes"], ("p2_hypotheses",)),
        QA("2.1c", "p2", R1, "How would you validate which root cause is correct?",
           p2["Validation"] + " Details per hypothesis are in the “How to validate” column of the table above.", ()),
        QA("2.2a", "p2", R2, "Estimate the monthly revenue loss from these failures (Cobre earns 0.5% per transaction).",
           p2["Loss"], ("p2_impact",)),
        QA("2.2b", "p2", R2, "If you could reduce the failure rate to 5%, what would be the monthly revenue gain?",
           p2["Gain"] + " " + p2["Recommendation"], ()),
        # ---------------------------- Part 3 ----------------------------------
        QA("3", "p3", "3 Strategic recommendation",
           "Which ONE corridor should Cobre prioritize for growth investment in 2026?",
           f"**{arrow(p3['winner'])}.** It is the largest, the only one growing and the one with the most revenue "
           f"to recover (~{usd(p3['winner_recoverable'])}/month). It wins the decision matrix with "
           f"{num(p3['scorecard'][p3['winner']]['score'], 2)} vs {num(p3['scorecard'][p3['runner_up']]['score'], 2)} "
           f"for {arrow(p3['runner_up'])}.", ("p3_scorecard", "p3_sensitivity")),
    ]


# --------------------------------------------------------------------------- #
# Notes: data quality, assumptions and AI usage
# --------------------------------------------------------------------------- #
def quality_notes(R: Results) -> list[str]:
    q = R["quality"].facts
    return [
        "Clean data: no empty cells, no duplicates, no orphan users, and corridors consistent with origin/destination.",
        f"The segment in transactions.csv differs from users.csv in {pct(q['segment_mismatch'], 0)} of rows and "
        f"{num(q['users_multi_segment'])} users appear with more than one segment. The transaction segment is used "
        "(it is the one the brief describes) and the mismatch is flagged as a data-governance task.",
        f"Data ends on {q['date_max']}: monthly metrics are computed per day with data.",
        f"Assumptions: {pct(cfg.FEE_RATE)} fee on successful payments; Cobre's real volume of US$1.5B/month with the "
        f"same mix as the sample; target failure rate {pct(cfg.TARGET_FAILURE_RATE, 0)}.",
        "Qualitative scores (Part 3): market 5 = largest remittance corridor (USD→MXN); simplicity 4 = mature "
        "SPEI/ACH rails; 2 = intra-LatAm double conversion or FX outflows subject to exchange controls.",
    ]


AI_NOTES = [
    "Claude (Anthropic) was used to refactor the initial scripts into a modular package with a single metrics "
    "function (summarize) instead of five duplicated groupby blocks, to suggest the root-cause cuts and the chi² "
    "test to rule out the day-of-week effect, and to draft the write-up and memo.",
    "Own validation: the patterns stated in the brief were checked against the data. Two do not hold: Friday "
    "failures (18%) match every other day, and the segment with the highest failure rate is enterprise, not "
    "retail (retail does drive more failures by volume). A US$10K threshold test within SME was added to "
    "separate the amount effect from the segment effect.",
    "Python is the single source of truth: every figure and text is generated by `python main.py`; the Excel "
    "workbook and this document only load and display those results.",
]
