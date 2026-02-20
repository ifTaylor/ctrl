from __future__ import annotations
import numpy as np

from ctrl.models import KalmanRunConfig


def run_procedural_kalman(
    t_s: np.ndarray,
    x: np.ndarray,
    cfg: KalmanRunConfig,
) -> tuple[np.ndarray, np.ndarray]:
    n = len(x)
    y = np.empty(n, dtype=float)
    y_dot = np.empty(n, dtype=float)

    x_pred = float(x[0])
    x_dot_pred = 0.0

    P00 = float(cfg.p00)
    P01 = float(cfg.p01)
    P10 = float(cfg.p01)
    P11 = float(cfg.p11)

    y[0] = x_pred
    y_dot[0] = x_dot_pred

    for k in range(1, n):
        dt_s = float(t_s[k] - t_s[k - 1])
        if not np.isfinite(dt_s) or dt_s <= 0.0:
            # pass-through
            y[k] = float(x[k])
            y_dot[k] = 0.0
            continue

        # PREDICT
        x_pred = x_pred + (dt_s * x_dot_pred)

        # Tracking covariance (scalar expanded intentionally avoiding matrices)
        xcov00 = (P00 + dt_s * P10) + dt_s * (P01 + dt_s * P11)
        xcov01 = (P01 + dt_s * P11)
        xcov10 = (P10 + dt_s * P11)
        xcov11 = (P11)

        # Accounting for process noise
        xcov00 = xcov00 + cfg.q_x
        xcov11 = xcov11 + cfg.q_x_dot

        # UPDATE
        y_res = float(x[k] - x_pred)
        S = xcov00 + cfg.r_x

        if S > 0.0 and np.isfinite(S):
            K0 = xcov00 / S
            K1 = xcov10 / S

            x_pred = x_pred + (K0 * y_res)
            x_dot_pred = x_dot_pred + (K1 * y_res)

            if cfg.bleed_enable:
                if abs(x[k] - x_pred) < cfg.bleed_thresh:
                    x_dot_pred = x_dot_pred * cfg.bleed_factor

            # Tracking covariance
            P00 = (1.0 - K0) * xcov00
            P01 = (1.0 - K0) * xcov01
            P10 = xcov10 - (K1 * xcov00)
            P11 = xcov11 - (K1 * xcov01)

            # Enforcing symmetry
            P10 = P01

        y[k] = x_pred
        y_dot[k] = x_dot_pred

    return y, y_dot
