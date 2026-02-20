from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class TimeSeriesData:
    t: np.ndarray
    x: np.ndarray
    dt_s: float
    source_path: str
