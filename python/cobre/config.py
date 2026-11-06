"""Central configuration: paths, business assumptions and catalogs.

Every value that used to be hard-coded across several scripts lives here once.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
# Expected layout:  Assesment/{transactions.csv, users.csv, python/, outputs/}
PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("COBRE_DATA_DIR", PROJECT_DIR))
OUTPUT_DIR = Path(os.getenv("COBRE_OUTPUT_DIR", PROJECT_DIR / "outputs"))

TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
USERS_FILE = DATA_DIR / "users.csv"

# --------------------------------------------------------------------------- #
# Business assumptions (from the assessment brief)
# --------------------------------------------------------------------------- #
FEE_RATE = 0.005                    # Cobre earns 0.5% per successful transaction
TARGET_FAILURE_RATE = 0.05          # target failure rate for the problem corridor
COBRE_MONTHLY_VOLUME_USD = 1.5e9    # Cobre's real monthly volume, used to scale the sample
PROBLEM_CORRIDOR = "USD_MXN"

# --------------------------------------------------------------------------- #
# Catalogs
# --------------------------------------------------------------------------- #
SUCCESS, FAILED = "success", "failed"

WEEKDAYS = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
            4: "Friday", 5: "Saturday", 6: "Sunday"}

# Amount bands (USD). The 10k cut-off is the one named in the brief.
AMOUNT_BINS = [0, 1_000, 2_500, 5_000, 10_000, float("inf")]
AMOUNT_LABELS = ["<1k", "1k-2.5k", "2.5k-5k", "5k-10k", ">10k"]
THRESHOLD_USD = 10_000

CATEGORICAL_COLUMNS = ["corridor", "status", "source_country",
                       "destination_country", "user_segment"]

# --------------------------------------------------------------------------- #
# Part 3 · Decision matrix
# --------------------------------------------------------------------------- #
# Criterion weights (must add up to 1). Quantitative criteria come from the data;
# "market" and "simplicity" are qualitative judgments documented in the report.
SCORE_WEIGHTS = {
    "revenue_month_scaled": 0.30,   # current volume and revenue
    "growth_q4_vs_q3":      0.15,   # trend
    "success_rate":         0.15,   # reliability
    "recoverable_revenue":  0.20,   # immediate improvement opportunity
    "market_score":         0.10,   # market size (1-5)
    "simplicity_score":     0.10,   # 5 = simple operation
}

# 1-5 scale. Rationale:
#  - USD_MXN: world's largest remittance corridor (US -> Mexico), mature SPEI rails.
#  - USD_COP: growing remittance and B2B flows into Colombia, PSE/ACH rails.
#  - MXN_COP: intra-LatAm without USD, double conversion and cross liquidity.
#  - COP_USD / MXN_USD: FX outflows, more exchange controls and reporting.
MARKET_SCORE = {"USD_MXN": 5, "USD_COP": 4, "MXN_COP": 3, "COP_USD": 2, "MXN_USD": 3}
SIMPLICITY_SCORE = {"USD_MXN": 4, "USD_COP": 4, "MXN_COP": 2, "COP_USD": 2, "MXN_USD": 3}
