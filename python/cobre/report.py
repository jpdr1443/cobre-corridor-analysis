"""Markdown report. Formatting only: text lives in `answers.py`, figures in the Result tables."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import answers as A
from .fmt import arrow, cell, kind, label
from .result import Result


def md_table(df: pd.DataFrame, kinds: dict[str, str] | None = None) -> str:
    kinds = kinds or {}
    d = df.reset_index() if df.index.name or isinstance(df.index, pd.MultiIndex) else df.copy()
    cells = []
    for c in d.columns:
        k = kinds.get(str(c)) or kind(str(c), d[c].dropna().iloc[0] if d[c].notna().any() else None)
        cells.append(d[c].map(lambda v, k=k: cell(v, k)))
    body = pd.concat(cells, axis=1)
    head = "| " + " | ".join(label(str(c)) for c in d.columns) + " |"
    rows = ["| " + " | ".join(r) + " |" for r in body.astype(str).itertuples(index=False)]
    return "\n".join([head, "|" + "---|" * len(d.columns), *rows])


def _qa_section(R: dict[str, Result], items: list[A.QA]) -> str:
    out, topic = [], None
    tables = {k: v for r in R.values() for k, v in r.tables.items()}
    for q in items:
        if q.topic != topic:
            topic = q.topic
            out.append(f"\n### {topic}")
        out.append(f"\n**{q.code} · {q.question}**\n\n{q.answer}\n")
        out.extend(md_table(tables[t]) + "\n" for t in q.tables)
    return "\n".join(out)


def write(results: list[Result], path: Path) -> Path:
    R = {r.name: r for r in results}
    qas = A.qa(R)
    part = lambda p: [q for q in qas if q.code.startswith(p)]  # noqa: E731
    wu = "\n\n".join(f"**{h}.** {t}" for h, t in A.p2_writeup(R))
    memo = "\n\n".join(f"**{h}:** {t}" for h, t in A.p3_memo(R))
    corridor = arrow(R["p2_root_cause"].facts["corridor"])

    text = "\n".join([
        "# Cobre · Transaction Corridor Analysis (Jul–Dec 2025)",
        "\n## Executive summary",
        *(f"{i}. {t}" for i, t in enumerate(A.executive_summary(R), 1)),
        "\n## Part 1 · Data analysis", _qa_section(R, part("1")),
        f"\n## Part 2 · Root cause of {corridor} failures",
        f"\n### Write-up ({A.words(A.p2_writeup(R))} words)\n\n{wu}\n",
        "### Answers and supporting tables", _qa_section(R, part("2")),
        f"\n## Part 3 · Recommendation memo ({A.words(A.p3_memo(R))} words)\n\n{memo}\n",
        _qa_section(R, part("3")),
        "\n## Data quality and assumptions", md_table(R["quality"].tables["q_checks"]),
        *(f"- {n}" for n in A.quality_notes(R)),
        "\n## Use of AI tools", *(f"- {n}" for n in A.AI_NOTES), "",
    ])
    path.write_text(text, encoding="utf-8")
    return path
