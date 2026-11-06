"""Written deliverable (Word + PDF), generated from the same source as everything else.

Usage:
    python build_document.py   # -> ../outputs/Cobre_Assessment_Deliverable.docx (+ .pdf if LibreOffice exists)

Layout (one document, easy to walk through):
    Page 1  One-page summary: KPIs, 5 key findings, chart, recommendation
    Page 2  Part 1 · Data analysis: every question with its answer
    Page 3  Part 2 · Root-cause write-up (250-300 words) + evidence + revenue impact
    Page 4  Part 3 · Recommendation memo (≤400 words) + decision matrix
    Page 5  Appendix: use of AI, data quality and assumptions, deliverables
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib
import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from cobre import answers as A
from cobre import config as cfg
from cobre import part1, part2, part3, quality
from cobre.data import get_data, load_raw
from cobre.fmt import arrow, cell, kind, label, pct, usd
from cobre.part2 import SAMPLE, SCALED, BRIEF

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DARK, COPPER, SAGE, BAD, GREY, LIGHT = "324646", "B87333", "7FA39D", "D64550", "6B7280", "F2F4F3"
FONT = "Arial"
OUT_NAME = "Cobre_Assessment_Deliverable"


# --------------------------------------------------------------------------- #
# Word helpers
# --------------------------------------------------------------------------- #
def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


def rich(par, text: str, size: float = 10, color: str | None = None, bold: bool = False):
    """Add text to a paragraph, turning **...** into bold runs."""
    for i, chunk in enumerate(re.split(r"\*\*", text)):
        if not chunk:
            continue
        run = par.add_run(chunk)
        run.font.size, run.font.name = Pt(size), FONT
        run.bold = bold or i % 2 == 1
        if color:
            run.font.color.rgb = rgb(color)
    return par


def para(doc, text="", size=10, color=None, bold=False, after=4, before=0, style=None, align=None):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after, p.paragraph_format.space_before = Pt(after), Pt(before)
    if align is not None:
        p.alignment = align
    if text:
        rich(p, text, size, color, bold)
    return p


def heading(doc, text, size=14, color=DARK, before=6, after=4):
    p = para(doc, text, size=size, color=color, bold=True, before=before, after=after)
    p.paragraph_format.keep_with_next = True
    _bottom_border(p, COPPER if size >= 14 else "D1D5DB")
    return p


def bullet(doc, text, size=10, after=2):
    p = para(doc, style="List Bullet", after=after)
    rich(p, text, size)
    return p


def page_break(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def _bottom_border(p, color):
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in {"w:val": "single", "w:sz": "6", "w:space": "1", "w:color": color}.items():
        b.set(qn(k), v)
    bdr.append(b)
    pPr.append(bdr)


def _shade(c, color):
    tcPr = c._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    for k, v in {"w:val": "clear", "w:color": "auto", "w:fill": color}.items():
        shd.set(qn(k), v)
    tcPr.append(shd)


def _cell_text(c, text, size=8.5, bold=False, color=None, align=None):
    c.text = ""
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    if align is not None:
        p.alignment = align
    rich(p, str(text), size, color, bold)


def df_table(doc, df: pd.DataFrame, widths: list[float] | None = None, size=8.5):
    """pandas -> Word table using the shared labels/formats from fmt.py."""
    d = df if isinstance(df.index, pd.RangeIndex) else df.reset_index()
    t = doc.add_table(rows=1, cols=len(d.columns))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    for j, name in enumerate(d.columns):
        _cell_text(t.rows[0].cells[j], label(str(name)), size, True, "FFFFFF")
        _shade(t.rows[0].cells[j], COPPER)
    for rec in d.itertuples(index=False):
        cells = t.add_row().cells
        for j, (name, v) in enumerate(zip(d.columns, rec)):
            k = kind(str(name), v)
            _cell_text(cells[j], cell(v, k), size, bold=(j == 0))
    if widths:
        set_widths(t, widths)
    para(doc, after=2)
    return t


def set_widths(t, widths: list[float]):
    """Fixed column widths (Word ignores cell widths unless autofit is off and the grid is set)."""
    t.autofit = False
    for j, w in enumerate(widths):
        t.columns[j].width = Inches(w)
        for c in t.columns[j].cells:
            c.width = Inches(w)


def kpi_strip(doc, items: list[tuple[str, str, str]]):
    t = doc.add_table(rows=2, cols=len(items))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, (cap, val, color) in enumerate(items):
        top, bottom = t.rows[0].cells[j], t.rows[1].cells[j]
        _cell_text(top, cap, 7.5, True, GREY, align=1)
        _cell_text(bottom, val, 15, True, color, align=1)
        _shade(top, LIGHT)
        _shade(bottom, LIGHT)
    para(doc, after=2)


# --------------------------------------------------------------------------- #
# Charts (matplotlib, from the Result tables)
# --------------------------------------------------------------------------- #
def _style(ax, title):
    ax.set_title(title, fontsize=9, fontweight="bold", color="#1F2937", loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=7.5)
    ax.yaxis.grid(True, color="#E5E7EB", linewidth=0.6)
    ax.set_axisbelow(True)


def _bars(ax, labels, values, colors, fmt="{:.1%}", rotate=0):
    bars = ax.bar(labels, values, color=colors, width=0.62)
    for b, v in zip(bars, values):
        ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom",
                    fontsize=7, xytext=(0, 1.5), textcoords="offset points")
    ax.tick_params(axis="x", rotation=rotate)


def _paired(ax, df, title, short=False):
    x = range(len(df))
    ax.bar([i - 0.2 for i in x], df["corridor_failure_rate"], 0.4, color=f"#{BAD}", label="USD→MXN")
    ax.bar([i + 0.2 for i in x], df["rest_failure_rate"], 0.4, color=f"#{GREY}", label="Other corridors")
    ax.set_xticks(list(x), [str(i)[:3] if short else str(i) for i in df.index])
    ax.set_ylim(0, df["corridor_failure_rate"].max() * 1.2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    _style(ax, title)


def make_charts(R, tmp: Path) -> dict[str, Path]:
    T = {k: v for r in R.values() for k, v in r.tables.items()}
    out = {}
    s = T["p1_corridor_summary"]
    names = [arrow(c) for c in s.index]
    red = [f"#{BAD}" if c == cfg.PROBLEM_CORRIDOR else f"#{DARK}" for c in s.index]

    # Page 1: the story in one figure
    fig, ax = plt.subplots(1, 3, figsize=(7.4, 2.05), dpi=200)
    _bars(ax[0], names, s["pct_usd"], [f"#{COPPER}"] * 5, "{:.0%}", rotate=30)
    _style(ax[0], "Share of value")
    ax[0].set_ylim(0, s["pct_usd"].max() * 1.2)
    ax[1].set_ylim(0, s["failure_rate"].max() * 1.2)
    _bars(ax[1], names, s["failure_rate"], red, rotate=30)
    _style(ax[1], "Failure rate by corridor")
    _paired(ax[2], T["p2_by_segment"], "USD→MXN vs others, by segment")
    ax[2].legend(fontsize=6.5, frameon=False, loc="upper right")
    ax[2].set_ylim(0, T["p2_by_segment"]["corridor_failure_rate"].max() * 1.35)
    for a in ax[:2]:
        a.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    fig.tight_layout()
    out["summary"] = _save(fig, tmp / "summary.png")

    # Page 2: Part 1 patterns
    fig, ax = plt.subplots(1, 3, figsize=(7.4, 1.9), dpi=200)
    _bars(ax[0], names, s["num_tx"], [f"#{DARK}"] * 5, "{:,.0f}", rotate=30)
    _style(ax[0], "Transactions by corridor")
    ax[0].set_ylim(0, s["num_tx"].max() * 1.2)
    m = T["p1_month"]
    ax[1].plot([x[5:] for x in m.index], m["tx_per_day"], color=f"#{DARK}", marker="o", ms=3)
    ax[1].set_ylim(0, m["tx_per_day"].max() * 1.25)
    _style(ax[1], "Tx per day by month (2025)")
    w = T["p1_weekday"]
    _bars(ax[2], [d[:3] for d in w.index], w["tx_per_day"], [f"#{SAGE}"] * 7, "{:.0f}")
    ax[2].set_ylim(0, w["tx_per_day"].max() * 1.25)
    _style(ax[2], "Tx per day by weekday")
    fig.tight_layout()
    out["part1"] = _save(fig, tmp / "part1.png")

    # Page 3: Part 2 evidence
    fig, ax = plt.subplots(1, 3, figsize=(7.4, 1.95), dpi=200)
    _paired(ax[0], T["p2_by_amount_band"].dropna(subset=["corridor_failure_rate"]), "Failure by amount (USD)")
    th = T["p2_threshold_sme"]
    _bars(ax[1], [str(i).replace("k-", "-") for i in th.index], th["corridor_failure_rate"],
          [f"#{COPPER}"] * len(th), rotate=30)
    ax[1].set_ylim(0, th["corridor_failure_rate"].max() * 1.2)
    ax[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    _style(ax[1], "SME only: jump above US$10K")
    _paired(ax[2], T["p2_by_weekday"], "Failure by weekday (no Friday effect)", short=True)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.legend(*ax[0].get_legend_handles_labels(), loc="upper right", ncol=2, fontsize=7, frameon=False)
    out["part2"] = _save(fig, tmp / "part2.png")
    return out


def _save(fig, path: Path) -> Path:
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def page_summary(doc, R, charts):
    c, p2, p3 = R["p1_corridors"].facts, R["p2_root_cause"].facts, R["p3_strategy"].facts
    para(doc, "Cobre · Transaction Corridor Analysis", size=20, color=DARK, bold=True, after=0)
    para(doc, "L2 Business Architect Assessment · Candidate submission · Data: 50,000 transactions and 5,000 users, "
              "Jul–Dec 2025", size=9, color=GREY, after=6)
    heading(doc, "One-page summary", before=0)
    kpi_strip(doc, [
        ("Transactions", f"{R['quality'].facts['n_tx']:,}", DARK),
        ("Value processed", usd(c["total_usd"]), DARK),
        ("Success rate", pct(c["overall_success"]), DARK),
        (f"{arrow(p2['corridor'])} failure", pct(p2["failure_rate"]), BAD),
        ("Recoverable / month", usd(p3["winner_recoverable"]), COPPER),
    ])
    heading(doc, "Key findings", size=11, before=2)
    for t in A.executive_summary(R):
        bullet(doc, t, 9.5)
    doc.add_picture(str(charts["summary"]), width=Inches(7.0))
    doc.paragraphs[-1].paragraph_format.space_after = Pt(2)

    heading(doc, f"Recommendation: prioritize {arrow(p3['winner'])} in 2026", size=11, before=2)
    memo = dict(A.p3_memo(R))
    para(doc, f"Fix first, then grow. {memo['Hidden upside']}", size=9.5, after=3)
    for h, t in A.p3_memo(R):
        if h.startswith("Action"):
            bullet(doc, f"**{h.replace('Action ', '')}:** {t}", 9)
    para(doc, f"**Expected impact:** {memo['Expected impact']}", size=9.5, before=2, after=0)


def page_part1(doc, R, charts):
    heading(doc, "Part 1 · Data analysis", before=0)
    para(doc, "Every answer below is computed in Python; tables and charts are in Cobre_Dashboard.xlsx and "
              "Part1_Data_Analysis.xlsx.", size=8.5, color=GREY, after=4)
    doc.add_picture(str(charts["part1"]), width=Inches(7.0))
    items = [q for q in A.qa(R) if q.code.startswith("1")]
    t = doc.add_table(rows=1, cols=2)
    t.style = "Table Grid"
    for j, h in enumerate(["Question", "Answer"]):
        _cell_text(t.rows[0].cells[j], h, 8.5, True, "FFFFFF")
        _shade(t.rows[0].cells[j], COPPER)
    topic = None
    for q in items:
        if q.topic != topic:
            topic = q.topic
            row = t.add_row().cells
            merged = row[0].merge(row[1])
            _cell_text(merged, topic, 8.5, True, DARK)
            _shade(merged, LIGHT)
        row = t.add_row().cells
        _cell_text(row[0], f"**{q.code}** {q.question}", 8)
        _cell_text(row[1], q.answer, 8)
    set_widths(t, [2.1, 5.0])


def page_part2(doc, R, charts):
    f = R["p2_root_cause"].facts
    wu = A.p2_writeup(R)
    heading(doc, f"Part 2 · Why does {arrow(f['corridor'])} fail? Root cause and impact", before=0)
    para(doc, f"Write-up · {A.words(wu)} words", size=8.5, color=GREY, after=3)
    for h, t in wu:
        para(doc, f"**{h}.** {t}", size=9.5, after=4)
    doc.add_picture(str(charts["part2"]), width=Inches(7.0))
    impact = R["p2_root_cause"].tables["p2_impact"][
        ["monthly_value_usd", "failed_value_share", "monthly_revenue_lost_usd", "monthly_gain_at_target_usd",
         "annual_gain_usd"]]
    para(doc, "Revenue impact (fee 0.5%; gain = (failed value % − 5%) × corridor value × fee)", size=8.5,
         color=GREY, after=2)
    df_table(doc, impact.loc[[SAMPLE, SCALED, BRIEF]], widths=[1.9, 1.15, 0.9, 1.05, 1.05, 1.05], size=8)


def page_part3(doc, R):
    heading(doc, "Part 3 · Strategic recommendation memo", before=0)
    memo = A.p3_memo(R)
    para(doc, f"{A.words(memo)} words", size=8.5, color=GREY, after=3)
    for h, t in memo:
        if h == "To":
            para(doc, f"**To:** {t}", size=9.5, after=6)
        elif h == "Recommendation":
            para(doc, t, size=13, color=COPPER, after=4)
        elif h == "Scale":
            para(doc, "Why this corridor", size=10.5, color=DARK, bold=True, before=2, after=2)
            bullet(doc, f"**{h}:** {t}", 9.5)
        elif h in ("Growth", "Hidden upside", "Market"):
            bullet(doc, f"**{h}:** {t}", 9.5)
        elif h.startswith("Action"):
            if h.endswith("Stabilize"):
                para(doc, "Recommended actions", size=10.5, color=DARK, bold=True, before=4, after=2)
            bullet(doc, f"**{h.replace('Action ', '')}:** {t}", 9.5)
        else:
            para(doc, f"**{h}:** {t}", size=9.5, before=3, after=3)
    sc = R["p3_strategy"].tables["p3_scorecard"][
        ["pct_usd", "revenue_month_scaled", "growth_q4_vs_q3", "success_rate", "recoverable_revenue",
         "market_score", "simplicity_score", "score"]]
    para(doc, "Decision matrix (min-max normalized, weighted)", size=8.5, color=GREY, before=4, after=2)
    df_table(doc, sc, widths=[0.85, 0.7, 1.05, 0.75, 0.75, 0.95, 0.65, 0.7, 0.7], size=7.5)


def page_appendix(doc, R):
    heading(doc, "Appendix · Use of AI, data quality and deliverables", before=0)
    para(doc, "Use of AI tools", size=10.5, color=DARK, bold=True, after=2)
    for n in A.AI_NOTES:
        bullet(doc, n.replace("`", ""), 9.5)
    para(doc, "Data quality and assumptions", size=10.5, color=DARK, bold=True, before=6, after=2)
    for n in A.quality_notes(R):
        bullet(doc, n, 9.5)
    para(doc, "Deliverables", size=10.5, color=DARK, bold=True, before=6, after=2)
    files = [
        ("Cobre_Assessment_Deliverable.docx / .pdf", "This document: summary, write-up, memo, AI note."),
        ("Cobre_Dashboard.xlsx", "Dashboard and one sheet per part: each question, answer, table and chart."),
        ("Part1/2/3 workbooks", "Every analysis table, one sheet per table (data quality checks in Part 1)."),
        ("python/ (code)", "Single source of truth. Run: python main.py → build_excel.py → build_document.py."),
    ]
    df_table(doc, pd.DataFrame(files, columns=["File", "Content"]), widths=[2.4, 4.7], size=8.5)


# --------------------------------------------------------------------------- #
def build(out_dir: Path | None = None) -> Path:
    tx_raw, _ = load_raw()
    df, users = get_data()
    results = [quality.run(tx_raw, users, df), *part1.run(df, users), part2.run(df), part3.run(df)]
    R = {r.name: r for r in results}
    out_dir = out_dir or cfg.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.left_margin = sec.right_margin = Inches(0.7)
    sec.top_margin = sec.bottom_margin = Inches(0.6)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    footer = sec.footer.paragraphs[0]
    rich(footer, "Cobre · L2 Business Architect Assessment · All figures generated by the Python pipeline",
         7.5, GREY)

    with tempfile.TemporaryDirectory() as tmp:
        charts = make_charts(R, Path(tmp))
        page_summary(doc, R, charts)
        page_break(doc)
        page_part1(doc, R, charts)
        page_break(doc)
        page_part2(doc, R, charts)
        page_break(doc)
        page_part3(doc, R)
        page_break(doc)
        page_appendix(doc, R)
        path = out_dir / f"{OUT_NAME}.docx"
        doc.save(path)
    print("Document ->", path)

    office = shutil.which("soffice") or shutil.which("libreoffice")
    if office:
        subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(path)],
                       check=True, capture_output=True, timeout=180)
        print("PDF      ->", out_dir / f"{OUT_NAME}.pdf")
    else:
        print("LibreOffice not found: export the PDF from Word (File → Save As → PDF).")
    return path


if __name__ == "__main__":
    build()
