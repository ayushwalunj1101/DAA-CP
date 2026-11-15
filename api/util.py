"""JSON helpers: NaN and infinity become null (JSON has no NaN)."""
from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np


def clean(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        v = float(value)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(value, np.integer):
        return int(value)
    return value


def records(columns: dict[str, Iterable], rename: dict[str, str] | None = None) -> list[dict]:
    """Column arrays -> list of row dicts with clean values."""
    rename = rename or {}
    keys = list(columns)
    cols = [list(columns[k]) for k in keys]
    names = [rename.get(k, k) for k in keys]
    return [{n: clean(col[i]) for n, col in zip(names, cols)} for i in range(len(cols[0]) if cols else 0)]
