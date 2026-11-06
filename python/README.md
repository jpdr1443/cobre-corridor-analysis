# Cobre · L2 Business Architect Assessment — Python pipeline

Solves the three parts of the assessment and generates every deliverable from a single source of truth.

## How to run
```bash
cd python
pip install -r requirements.txt
python main.py            # full analysis -> ../outputs (tables per part + Markdown report)
python build_excel.py     # presentation workbook -> ../outputs/Cobre_Dashboard.xlsx
python build_document.py  # written deliverable -> ../outputs/Cobre_Assessment_Deliverable.docx / .pdf
```
The analysis walkthrough is in `../notebooks/analysis.ipynb` (it imports this package; no duplicated logic).
Input CSVs (`transactions.csv`, `users.csv`) are read from the parent folder.
Override with the `COBRE_DATA_DIR` and `COBRE_OUTPUT_DIR` environment variables.

## Structure
```
python/
├── main.py              # orchestrates: quality -> P1 -> P2 -> P3 -> export -> report
├── build_excel.py       # Excel workbook: loads values, charts and text (no formulas)
├── build_document.py    # Word + PDF deliverable (summary, write-up, memo, AI note)
└── cobre/
    ├── config.py        # paths, assumptions (0.5% fee, 5% target, US$1.5B), catalogs, P3 weights
    ├── data.py          # SINGLE load + enrichment (dates, flags, amount bands, user profile)
    ├── metrics.py       # summarize() and generic cuts: replace the repeated groupby blocks
    ├── result.py        # Result(tables, facts) container
    ├── quality.py       # Part 0: data validation and quality checks
    ├── part1.py         # Part 1: corridors, users, time
    ├── part2.py         # Part 2: USD→MXN root cause, chi², 10K threshold, impact
    ├── part3.py         # Part 3: decision matrix + sensitivity
    ├── answers.py       # SINGLE source of text: answers per question, write-up, memo, story
    ├── report.py        # Markdown report (formatting only)
    ├── export.py        # one Excel workbook per part + data model (CSV)
    ├── fmt.py           # number formatting + column labels/types
    └── xl.py            # reusable openpyxl styles, KPIs and charts
```

## What changed vs the original scripts
| Before | Now |
|---|---|
| 6 scripts, each reading the CSVs and recreating `is_success` | `data.get_data()` loads and enriches once (cached) |
| 5 nearly identical `groupby().agg()` blocks | `metrics.summarize(df, by)` for any grouping |
| Corridor-vs-rest comparison written by hand | `metrics.segment_vs_rest(df, mask, by)` |
| Constants repeated (days, amounts, 0.5%) | `config.py` |
| Parts 2 and 3 not solved | `part2.py`, `part3.py` and `answers.py` |

The original scripts were removed: this package fully replaces them.

## Outputs (`../outputs/`)
- `Cobre_Assessment_Deliverable.docx` / `.pdf` — the written deliverable: one-page summary, answers to Part 1,
  root-cause write-up (250-300 words), recommendation memo (≤400 words), data quality and AI usage.
- `Cobre_Dashboard.xlsx` — presentation workbook: dashboard with the story, one sheet per part with every
  question, its answer, tables and charts. **No calculation formulas** and no row-level data: Python is the
  single source of truth; to change anything, edit the code and regenerate.
- `Part1_Data_Analysis.xlsx`, `Part2_Root_Cause.xlsx`, `Part3_Recommendation.xlsx` — every analysis table,
  one sheet per table, with a clickable index (data quality checks are in Part 1).
- `findings_report.md` — the same content as plain Markdown.
- `fact_transactions.csv`, `dim_users.csv` — row-level data model for Excel / Power BI / SQL (not versioned).
