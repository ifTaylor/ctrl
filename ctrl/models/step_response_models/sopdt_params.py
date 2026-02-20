from dataclasses import dataclass


@dataclass(frozen=True)
class SOPDTUnderdampedParams:
    K: float = 1.0
    zeta: float = 0.45
    wn: float = 6.0
    theta_s: float = 0.0
