"""Common container for what each part of the analysis returns."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Result:
    name: str
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    facts: dict[str, object] = field(default_factory=dict)

    def add(self, key: str, table: pd.DataFrame) -> pd.DataFrame:
        self.tables[key] = table
        return table
