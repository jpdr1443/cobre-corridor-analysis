"""openpyxl helpers: styles, pandas tables, text blocks and charts."""
from __future__ import annotations

import math

import pandas as pd
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .fmt import EXCEL_FORMATS, kind, label

# Cobre palette
DARK, COPPER, SAGE, SAND = "324646", "B87333", "7FA39D", "D9A27E"
INK, GREY, LIGHT, BAD = "1F2937", "4B5563", "F5F6F8", "D64550"
FONT = "Arial"

_thin = Side(style="thin", color="D1D5DB")
BOX = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def font(size=10, bold=False, color=INK, italic=False):
    return Font(name=FONT, size=size, bold=bold, color=color, italic=italic)


def fill(color):
    return PatternFill("solid", start_color=color, end_color=color)


def col(n: int) -> str:
    return get_column_letter(n)


def widths(ws, mapping: dict[str, float]):
    for k, v in mapping.items():
        ws.column_dimensions[k].width = v


# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #
def title(ws, text, subtitle=None, row=2):
    ws.cell(row=row, column=2, value=text).font = font(18, True, DARK)
    if subtitle:
        ws.cell(row=row + 1, column=2, value=subtitle).font = font(10, color=GREY, italic=True)


def band(ws, row, text, c1=2, c2=12, color=DARK):
    """Full-width section band."""
    c = ws.cell(row=row, column=c1, value=text)
    c.font = font(11, True, "FFFFFF")
    for j in range(c1, c2 + 1):
        ws.cell(row=row, column=j).fill = fill(color)
    return row + 1


def paragraph(ws, row, text, c1=2, c2=12, size=10, bold=False, color=INK, bg=None,
              chars_per_line=None) -> int:
    """Wrapped text in merged cells; computes row height. Returns the next row."""
    ws.merge_cells(start_row=row, start_column=c1, end_row=row, end_column=c2)
    c = ws.cell(row=row, column=c1, value=text.replace("**", ""))
    c.font = font(size, bold, color)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    if bg:
        for j in range(c1, c2 + 1):
            ws.cell(row=row, column=j).fill = fill(bg)
    width = chars_per_line or sum((ws.column_dimensions[col(j)].width or 9) for j in range(c1, c2 + 1)) * 1.1
    lines = sum(max(1, math.ceil(len(p) / width)) for p in text.split("\n"))
    ws.row_dimensions[row].height = max(15, 14 * lines * size / 10 + 4)
    return row + 1


def link(ws, row, column, text, target_sheet, size=10, bold=False):
    c = ws.cell(row=row, column=column, value=text)
    c.hyperlink = f"#'{target_sheet}'!A1"
    c.font = Font(name=FONT, size=size, bold=bold, color=COPPER, underline="single")
    return c


def kpi(ws, row, column, caption, value, fmt, span=3, color=DARK):
    ws.merge_cells(start_row=row, start_column=column, end_row=row, end_column=column + span - 1)
    ws.merge_cells(start_row=row + 1, start_column=column, end_row=row + 2, end_column=column + span - 1)
    a = ws.cell(row=row, column=column, value=caption)
    a.font = font(9, True, GREY)
    b = ws.cell(row=row + 1, column=column, value=value)
    b.font = font(20, True, color)
    b.number_format = fmt
    for r in range(row, row + 3):
        for j in range(column, column + span):
            ws.cell(row=r, column=j).fill = fill(LIGHT)
    a.alignment = b.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def write_df(ws, row: int, c0: int, df: pd.DataFrame, kinds: dict[str, str] | None = None,
             spans: dict[str, int] | None = None) -> dict:
    """Write a DataFrame (index included) with labels and formats from `fmt.COLUMNS`.

    `spans` lets a text column span several Excel columns (merged cells).
    Returns {'header': row, 'first': row, 'last': row, 'cols': {name: excel_column}}.
    """
    kinds, spans = kinds or {}, spans or {}
    d = df if isinstance(df.index, pd.RangeIndex) else df.reset_index()
    positions, j = {}, c0
    for name in d.columns:
        positions[str(name)] = j
        j += spans.get(str(name), 1)
    last_col = j - 1

    for name, j in positions.items():
        span = spans.get(name, 1)
        if span > 1:
            ws.merge_cells(start_row=row, start_column=j, end_row=row, end_column=j + span - 1)
        h = ws.cell(row=row, column=j, value=label(name))
        h.font = font(10, True, "FFFFFF")
        h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for jj in range(j, j + span):
            ws.cell(row=row, column=jj).fill = fill(COPPER)
            ws.cell(row=row, column=jj).border = BOX
    ws.row_dimensions[row].height = 30

    for i, rec in enumerate(d.itertuples(index=False), start=row + 1):
        tallest = 1
        for name, value in zip(positions, rec):
            j, span = positions[name], spans.get(name, 1)
            if span > 1:
                ws.merge_cells(start_row=i, start_column=j, end_row=i, end_column=j + span - 1)
            if isinstance(value, float) and math.isnan(value):
                value = None
            elif hasattr(value, "item"):
                value = value.item()                         # numpy -> python
            k = kinds.get(name) or kind(name, value)
            c = ws.cell(row=i, column=j, value=value)
            c.font = font(10, bold=(j == c0))
            c.number_format = EXCEL_FORMATS[k]
            if k == "usd" and isinstance(value, (int, float)) and abs(value) >= 1e7:
                c.number_format = '"US$"#,##0.0,,"M"'          # millions so it fits
            if k == "text" and isinstance(value, str) and len(value) > 20:
                c.alignment = Alignment(wrap_text=True, vertical="top")
                width = sum((ws.column_dimensions[col(x)].width or 9) for x in range(j, j + span)) * 1.1
                tallest = max(tallest, math.ceil(len(value) / width))
            for jj in range(j, j + span):
                ws.cell(row=i, column=jj).border = BOX
        if tallest > 1:
            ws.row_dimensions[i].height = 14 * tallest + 4
    return {"header": row, "first": row + 1, "last": row + len(d), "cols": positions, "last_col": last_col}


# --------------------------------------------------------------------------- #
# Charts (always on cells with values already loaded)
# --------------------------------------------------------------------------- #
def chart(ws, kind_: str, pos: dict, values: list[str], ttl: str, anchor: str, colors=(DARK, COPPER, SAGE),
          y_fmt=None, y_min=None, y_max=None, labels=False, legend=None, width=15.5, height=7.2,
          horizontal=False, data_ws=None):
    """Bar or line chart from the table returned by `write_df` (in `data_ws`)."""
    src = data_ws or ws
    ch = LineChart() if kind_ == "line" else BarChart()
    if kind_ != "line":
        ch.type = "bar" if horizontal else "col"
        ch.gapWidth = 60
    for name, color in zip(values, colors):
        cidx = pos["cols"][name]
        ch.add_data(Reference(src, min_col=cidx, min_row=pos["header"], max_row=pos["last"]), titles_from_data=True)
        s = ch.series[-1]
        if kind_ == "line":
            s.graphicalProperties.line.solidFill = color
            s.graphicalProperties.line.width = 28000
            s.smooth = False
        else:
            s.graphicalProperties.solidFill = color
            s.graphicalProperties.line.solidFill = color
    first_col = min(pos["cols"].values())
    ch.set_categories(Reference(src, min_col=first_col, min_row=pos["first"], max_row=pos["last"]))
    ch.title, ch.style, ch.width, ch.height = ttl, 2, width, height
    ch.y_axis.majorGridlines = None
    ch.x_axis.delete = ch.y_axis.delete = False
    if y_fmt:
        ch.y_axis.numFmt = y_fmt
    if y_min is not None:
        ch.y_axis.scaling.min = y_min
    if y_max is not None:
        ch.y_axis.scaling.max = y_max
    if horizontal:
        ch.x_axis.scaling.orientation = "maxMin"
    if labels:
        ch.dataLabels = DataLabelList()
        ch.dataLabels.showVal = True
        ch.dataLabels.showSerName = ch.dataLabels.showCatName = ch.dataLabels.showLegendKey = False
    show_legend = len(values) > 1 if legend is None else legend
    if show_legend:
        ch.legend.position = "b"
    else:
        ch.legend = None
    ws.add_chart(ch, anchor)
    return ch
