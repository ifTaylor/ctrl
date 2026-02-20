from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class TuningResult:
    r_x: float
    sigma_x: float

    q_x_dot: float
    dv_count: int

    q_x_user: float
    q_x_consistent: float
    q_xv_consistent: float

    steady_span: Optional[Tuple[int, int]]
    ramp_span: Optional[Tuple[int, int]]
