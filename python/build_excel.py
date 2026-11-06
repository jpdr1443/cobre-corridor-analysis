"""Presentation workbook. Python is the single source of truth.

Usage:
    python build_excel.py            # -> ../outputs/Cobre_Dashboard.xlsx

The workbook has no calculation formulas: it loads the values produced by the pipeline
(`Result` tables) and the text from `cobre/answers.py`, and draws charts on those cells.
Row-level data is not embedded: it lives in outputs/fact_transactions.csv and dim_users.csv.
To change a number or a conclusion, change the Python code and regenerate the workbook.
"""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule

from cobre import answers as A
from cobre import config as cfg
from cobre import part1, part2, part3, quality
from cobre.data import get_data, load_raw
from cobre.export import WORKBOOKS
from cobre.fmt import EXCEL_FORMATS, arrow
from cobre.result import Result
from cobre.xl import (BAD, COPPER, DARK, GREY, LIGHT, SAGE, SAND, band, chart, col, font, kpi, link,
                      paragraph, title, widths, write_df)

NAV = ["Dashboard", "P1 Corridors", "P1 Users", "P1 Time", "P2 Root Cause",
       "P3 Recommendation", "Data Quality & AI", "Data Model"]
TABLE_END_COL = 12                          # text and tables in B:L

# --------------------------------------------------------------------------- #
# How each Python table is displayed: columns, chart and special formats
# --------------------------------------------------------------------------- #
PCT0 = "0%"
SPECS: dict[str, dict] = {
    "p1_top5_volume": dict(caption="Transactions by corridor",
                           chart=dict(kind_="bar", values=["num_tx"], labels=True)),
    "p1_top5_value": dict(caption="Transaction value by corridor",
                          chart=dict(kind_="bar", values=["total_usd"], colors=(COPPER,), y_fmt='"$"#,##0,,"M"')),
    "p1_success_rank": dict(caption="Success rate by corridor (axis starts at 70%)",
                            chart=dict(kind_="bar", values=["success_rate"], colors=(SAGE,), y_fmt=PCT0,
                                       y_min=0.7, y_max=1, labels=True)),
    "p1_ticket": dict(caption="Average and median ticket by corridor",
                      chart=dict(kind_="bar", values=["avg_ticket", "median_ticket"], colors=(DARK, SAND),
                                 y_fmt='"$"#,##0')),
    "p1_tx_per_user_stats": dict(caption="Transactions per user: statistics"),
    "p1_tx_per_user_distribution": dict(caption="Distribution: users by number of transactions",
                                        chart=dict(kind_="bar", values=["users"], colors=(SAGE,))),
    "p1_top10_users": dict(caption="Top 10 users (ties broken by value)"),
    "p1_country_comparison": dict(caption="By user country",
                                  cols=["users", "num_tx", "pct_tx", "total_usd", "tx_per_user", "avg_ticket",
                                        "success_rate"],
                                  chart=dict(kind_="bar", values=["tx_per_user"], colors=(DARK,), labels=True,
                                             y_min=0)),
    "p1_mx_co_inbound": dict(caption="Money ARRIVING in each country (by destination)",
                             cols=["num_tx", "total_usd", "avg_ticket", "failure_rate"],
                             chart=dict(kind_="bar", values=["failure_rate"], colors=(BAD,), y_fmt=PCT0,
                                        labels=True, y_min=0)),
    "p1_weekday": dict(caption="Volume by day of week (average per day with data)",
                       cols=["num_tx", "active_days", "tx_per_day", "success_rate"],
                       chart=dict(kind_="bar", values=["tx_per_day"], colors=(SAGE,), y_min=0)),
    "p1_hour": dict(caption="Volume by hour", cols=["num_tx", "pct_tx", "success_rate"],
                    chart=dict(kind_="bar", values=["num_tx"], colors=(DARK,), y_min=0)),
    "p1_heatmap_hour_weekday": dict(caption="Heatmap: transactions by hour × day", heat=True),
    "p1_month": dict(caption="Monthly trend", cols=["num_tx", "active_days", "tx_per_day", "tx_per_day_change",
                                                       "total_usd", "success_rate"],
                     chart=dict(kind_="line", values=["tx_per_day"], y_min=0, y_fmt="0")),
    "p2_by_segment": dict(caption="Failure by segment: USD→MXN vs other corridors",
                          chart=dict(kind_="bar", values=["corridor_failure_rate", "rest_failure_rate"],
                                     colors=(BAD, GREY), y_fmt=PCT0, y_min=0)),
    "p2_by_amount_band": dict(caption="Failure by amount", dropna="corridor_failure_rate",
                              chart=dict(kind_="bar", values=["corridor_failure_rate", "rest_failure_rate"],
                                         colors=(BAD, GREY), y_fmt=PCT0, y_min=0)),
    "p2_threshold_sme": dict(caption="US$10K threshold test: SME only, USD→MXN",
                             cols=["corridor_num_tx", "corridor_failed_tx", "corridor_failure_rate"],
                             chart=dict(kind_="bar", values=["corridor_failure_rate"], colors=(COPPER,), y_fmt=PCT0,
                                        labels=True, y_min=0)),
    "p2_by_weekday": dict(caption="Failure by day of week (no Friday effect)",
                          cols=["corridor_num_tx", "corridor_failure_rate", "rest_failure_rate"],
                          chart=dict(kind_="bar", values=["corridor_failure_rate", "rest_failure_rate"],
                                     colors=(BAD, GREY), y_fmt=PCT0, y_min=0)),
    "p2_significance": dict(caption="Chi² test: does failure depend on segment or day?",
                            spans={"conclusion": 4}),
    "p2_hypotheses": dict(caption="Hypotheses, evidence and validation",
                          spans={"hypothesis": 3, "evidence": 4, "how_to_validate": 4}),
    "p2_impact": dict(caption="Monthly revenue impact (0.5% fee)", spans={"scenario": 3},
                      cols=["monthly_value_usd", "failed_value_share", "monthly_revenue_lost_usd",
                            "monthly_gain_at_target_usd", "annual_gain_usd"],
                      chart=dict(kind_="bar", values=["monthly_revenue_lost_usd", "monthly_gain_at_target_usd"],
                                 colors=(BAD, SAGE), y_fmt='"$"#,##0,"k"')),
    "p3_scorecard": dict(caption="Decision matrix (min-max normalization, weights in config.py)",
                         cols=["pct_usd", "revenue_month_scaled", "growth_q4_vs_q3", "success_rate",
                               "recoverable_revenue", "market_score", "simplicity_score", "score", "rank"],
                         chart=dict(kind_="bar", values=["score"], colors=(DARK,), labels=True)),
    "p3_sensitivity": dict(caption="Sensitivity: winner when each criterion is removed", spans={"scenario": 3}),
    "q_checks": dict(caption="Data quality checks"),
}


# --------------------------------------------------------------------------- #
# Sheet helpers
# --------------------------------------------------------------------------- #
def new_sheet(wb, name, ttl, sub):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    widths(ws, {"A": 2, **{col(c): 14 for c in range(2, TABLE_END_COL + 1)}, "M": 3,
                **{col(c): 10 for c in range(14, 23)}})
    for i, sh in enumerate(NAV):
        if sh == name:
            ws.cell(row=1, column=2 + i, value=sh).font = font(9, True, DARK)
        else:
            link(ws, 1, 2 + i, sh, sh, size=9)
    title(ws, ttl, sub)
    return ws


def table_block(ws, row, key, tables) -> tuple[int, dict]:
    """Table (with its chart to the right, if any). Returns the next row and positions."""
    spec = SPECS.get(key, {})
    df = tables[key]
    if spec.get("dropna"):
        df = df.dropna(subset=[spec["dropna"]])
    if spec.get("cols"):
        df = df[spec["cols"]]
    ws.cell(row=row, column=2, value=spec.get("caption", key)).font = font(10, True, GREY, italic=True)
    pos = write_df(ws, row + 1, 2, df, spans=spec.get("spans"))
    if spec.get("heat"):
        rng = f"C{pos['first']}:{col(pos['last_col'])}{pos['last']}"
        ws.conditional_formatting.add(rng, ColorScaleRule(start_type="min", start_color="F2F5F4",
                                                          mid_type="percentile", mid_value=50, mid_color="A9C2BD",
                                                          end_type="max", end_color="324646"))
    end = pos["last"] + 2
    if spec.get("chart"):
        ch = dict(spec["chart"])
        anchor = f"{col(pos['last_col'] + 2)}{row}"                 # chart to the right of the table
        chart(ws, ch.pop("kind_"), pos, ch.pop("values"), spec.get("caption", key), anchor, **ch)
        end = max(end, row + 16)
    return end, pos


def qa_blocks(ws, row, items: list[A.QA], tables) -> tuple[int, dict]:
    topic, positions = None, {}
    for q in items:
        if q.topic != topic:
            topic = q.topic
            row = band(ws, row + 1, topic, c2=22) + 1
        ws.cell(row=row, column=2, value=f"{q.code} · {q.question}").font = font(11, True, COPPER)
        row = paragraph(ws, row + 1, q.answer, c2=TABLE_END_COL, bg=LIGHT) + 1
        for key in q.tables:
            row, positions[key] = table_block(ws, row, key, tables)
    return row, positions


def labeled_paragraphs(ws, row, items: list[tuple[str, str]], head: str) -> int:
    row = band(ws, row, head, c2=TABLE_END_COL)
    for h, t in items:
        row = paragraph(ws, row, f"{h}: {t}", c2=TABLE_END_COL)
    return row + 1


# --------------------------------------------------------------------------- #
# Sheets
# --------------------------------------------------------------------------- #
def sheet_dashboard(wb, R, qas, pos_p1, pos_p2):
    ws = wb["Dashboard"]
    ws.sheet_view.showGridLines = False
    widths(ws, {"A": 2, **{col(c): 12 for c in range(2, 20)}})
    for i, sh in enumerate(NAV[1:], start=1):
        link(ws, 1, 2 + (i - 1) * 2, sh, sh, size=9)
    title(ws, "Cobre · Transaction Corridor Analysis (Jul–Dec 2025)",
          "50,000 transactions · 5,000 users · 5 corridors. Every figure comes from the Python pipeline.")

    c, p2, p3 = R["p1_corridors"].facts, R["p2_root_cause"].facts, R["p3_strategy"].facts
    tiles = [("Transactions", R["quality"].facts["n_tx"], EXCEL_FORMATS["int"], DARK),
             ("Value processed", c["total_usd"], '"US$"#,##0.0,,"M"', DARK),
             ("Success rate", c["overall_success"], "0.0%", DARK),
             (f"{arrow(p2['corridor'])} failure rate", p2["failure_rate"], "0.0%", BAD),
             ("Recoverable / month (scaled)", p3["winner_recoverable"], '"US$"#,##0', COPPER),
             ("Corridor to prioritize 2026", arrow(p3["winner"]), "@", COPPER)]
    for i, (cap, val, fmt, color) in enumerate(tiles):
        kpi(ws, 5, 2 + i * 3, cap, val, fmt, span=3, color=color)

    row = band(ws, 9, "The story in 5 findings", c2=19)
    for i, t in enumerate(A.executive_summary(R), 1):
        ws.cell(row=row, column=2, value=i).font = font(14, True, COPPER)
        row = paragraph(ws, row, t, c1=3, c2=19, chars_per_line=170)

    row = band(ws, row + 1, "Corridor overview", c2=19) + 1
    summary = R["p1_corridors"].tables["p1_corridor_summary"][
        ["num_tx", "pct_tx", "total_usd", "pct_usd", "success_rate", "failure_rate", "avg_ticket"]]
    pos = write_df(ws, row, 2, summary)
    for r in range(pos["first"], pos["last"] + 1):           # highlight the problem corridor
        if ws.cell(row=r, column=2).value == cfg.PROBLEM_CORRIDOR:
            ws.cell(row=r, column=pos["cols"]["failure_rate"]).font = font(10, True, BAD)
    chart(ws, "bar", pos, ["failure_rate"], "Failure rate by corridor", f"K{row}", colors=(BAD,),
          y_fmt="0%", labels=True, y_min=0, width=17)
    row = max(pos["last"] + 2, row + 15)

    pm, ps = pos_p1["p1_month"], pos_p2["p2_by_segment"]
    chart(ws, "line", pm, ["tx_per_day"], "Flat volume: tx per day, by month", f"B{row}",
          y_min=0, y_fmt="0", width=17, data_ws=wb["P1 Time"])
    chart(ws, "bar", ps, ["corridor_failure_rate", "rest_failure_rate"], "USD→MXN fails 3-5× in every segment",
          f"K{row}", colors=(BAD, GREY), y_fmt="0%", y_min=0, width=17, data_ws=wb["P2 Root Cause"])
    row += 16

    row = band(ws, row, f"Recommendation: prioritize {arrow(p3['winner'])}", c2=19, color=COPPER)
    for h, t in A.p3_memo(R):
        if h.startswith("Action") or h == "Expected impact":
            row = paragraph(ws, row, f"{h}: {t}", c2=19, chars_per_line=190)

    row = band(ws, row + 1, "Assessment questions: where each answer is", c2=19) + 1
    for q in qas:
        ws.cell(row=row, column=2, value=q.code).font = font(10, True, DARK)
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=15)
        ws.cell(row=row, column=3, value=q.question).font = font(10)
        link(ws, row, 16, f"See {A.SHEETS[q.sheet]} →", A.SHEETS[q.sheet])
        row += 1


def sheet_qa(wb, name, ttl, sub, items, tables, pre=None):
    ws = new_sheet(wb, name, ttl, sub)
    row = 5
    if pre:
        row = pre(ws, row)
    _, pos = qa_blocks(ws, row, items, tables)
    return pos


def sheet_quality(wb, R):
    ws = new_sheet(wb, "Data Quality & AI", "Data quality, assumptions and use of AI",
                   "Checks run in Python before the analysis.")
    row, _ = table_block(ws, 5, "q_checks", {"q_checks": R["quality"].tables["q_checks"]})
    row = labeled_paragraphs(ws, row, [(f"Note {i}", t) for i, t in enumerate(A.quality_notes(R), 1)],
                             "Notes and assumptions")
    labeled_paragraphs(ws, row, [(f"{i}", t) for i, t in enumerate(A.AI_NOTES, 1)], "Use of AI tools")


SCHEMA = [
    ("Data", "Fact · 1 row per transaction (outputs/fact_transactions.csv, kept out of this workbook)", [
        ("transaction_id", "Text", "PK. Unique identifier", "CSV"),
        ("user_id", "Text", "FK → Users.user_id", "CSV"),
        ("transaction_date / transaction_time", "Date / Text", "Transaction date and time", "CSV"),
        ("hour, weekday_n, weekday, month, quarter", "Number / Text", "Calendar attributes", "Python"),
        ("corridor, source_country, destination_country", "Text", "Corridor and countries (US, MX, CO)", "CSV"),
        ("user_segment", "Text", "Segment at transaction time", "CSV"),
        ("user_segment_profile, country, user_status", "Text", "Profile attributes (joined from Users)", "Python"),
        ("amount_usd", "Decimal", "Amount in USD", "CSV"),
        ("amount_band, over_threshold", "Text / 0-1", "Amount band and >US$10K flag", "Python"),
        ("status, is_success, is_failed", "Text / 0-1", "Status and flags for rates", "CSV / Python"),
        ("success_usd, failed_usd", "Decimal", "Successful / failed amount", "Python"),
    ]),
    ("Users", "Dimension · 1 row per user (users.csv)", [
        ("user_id", "Text", "PK", "CSV"), ("country", "Text", "Mexico / Colombia", "CSV"),
        ("user_segment", "Text", "Profile segment", "CSV"),
        ("registration_date", "Date", "Registration date", "CSV"), ("status", "Text", "active / inactive", "CSV"),
    ]),
]


def sheet_model(wb, results: list[Result]):
    import pandas as pd
    ws = new_sheet(wb, "Data Model", "Data model and result tables",
                   "Data (fact) N → 1 Users. Result tables are generated by `python main.py`.")
    row = 5
    for tname, desc, cols in SCHEMA:
        df = pd.DataFrame(cols, columns=["Column", "Type", "Description", "Source"])
        row = band(ws, row, f"{tname} — {desc}", c2=TABLE_END_COL)
        row = write_df(ws, row, 2, df, spans={"Column": 4, "Description": 4})["last"] + 2
    row = band(ws, row, "Relationship: Data.user_id  N ──► 1  Users.user_id", c2=TABLE_END_COL, color=COPPER) + 1
    file_of = {m: f for f, (_, mods) in WORKBOOKS.items() for m in mods}
    index = pd.DataFrame([(k, file_of[r.name], len(t)) for r in results for k, t in r.tables.items()],
                         columns=["Table", "File", "Rows"])
    band(ws, row, "Python result tables (one workbook per part in outputs/)", c2=TABLE_END_COL)
    write_df(ws, row + 1, 2, index, spans={"Table": 3, "File": 3})


# --------------------------------------------------------------------------- #
def build(path=None):
    tx_raw, _ = load_raw()
    df, users = get_data()
    results = [quality.run(tx_raw, users, df), *part1.run(df, users), part2.run(df), part3.run(df)]
    R = {r.name: r for r in results}
    tables = {k: v for r in results for k, v in r.tables.items()}
    qas = A.qa(R)
    by_sheet = lambda key: [q for q in qas if q.sheet == key]  # noqa: E731

    wb = Workbook()
    wb.active.title = "Dashboard"
    sheet_qa(wb, "P1 Corridors", "Part 1.1 · Corridor performance",
             "Volume, value, success and ticket size by corridor.", by_sheet("p1_corr"), tables)
    sheet_qa(wb, "P1 Users", "Part 1.2 · User behavior",
             "Frequency, top 10 and Mexico vs Colombia.", by_sheet("p1_users"), tables)
    pos_p1 = sheet_qa(wb, "P1 Time", "Part 1.3 · Time patterns",
                      "Day of week, hour and monthly trend.", by_sheet("p1_time"), tables)
    pos_p2 = sheet_qa(wb, "P2 Root Cause", f"Part 2 · Why does {arrow(cfg.PROBLEM_CORRIDOR)} fail and what does it cost?",
                      "Answer to every question with its evidence (tables and charts generated in Python).",
                      by_sheet("p2"), tables,
                      pre=lambda ws, r: paragraph(
                          ws, r, f"Write-up ({A.words(A.p2_writeup(R))} words): answers 2.1a → 2.2b, read in order, "
                          "make up the full deliverable text. Each one sits next to its evidence.",
                          c2=TABLE_END_COL, bold=True, color=DARK) + 1)
    sheet_qa(wb, "P3 Recommendation", "Part 3 · Corridor to prioritize in 2026",
             "Recommendation memo (≤400 words) and decision matrix.", by_sheet("p3"), tables,
             pre=lambda ws, r: labeled_paragraphs(ws, r, A.p3_memo(R), "Recommendation memo"))
    sheet_quality(wb, R)
    sheet_model(wb, results)
    sheet_dashboard(wb, R, qas, pos_p1, pos_p2)

    wb._sheets = [wb[n] for n in NAV]
    for n in NAV[:6]:
        wb[n].sheet_properties.tabColor = COPPER
    wb.active = 0

    path = path or cfg.OUTPUT_DIR / "Cobre_Dashboard.xlsx"
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print("Workbook ->", path)
    return path


if __name__ == "__main__":
    build()
