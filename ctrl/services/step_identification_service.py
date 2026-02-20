from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Literal

import numpy as np

from ctrl.models import StepIdResult, StepTuneSelections

PVModelType = Literal["FOPDT", "IPDT", "SOPDT_UNDERDAMPED"]
TuningMethod = Literal["IMC_PID", "IMC_PI", "SIMC_PI"]


@dataclass
class StepSeries:
    t: np.ndarray
    cv: np.ndarray
    pv: np.ndarray
    dt_s: float
    source_path: str = ""
    pv_raw: Optional[np.ndarray] = None


def load_step_csv(
    path: str,
    *,
    time_unit: str = "s",
    time_col: str = "time",
    cv_col: Optional[str] = "CV",
    pv_col: str = "PV",
) -> StepSeries:
    try:
        data = np.genfromtxt(path, delimiter=",", names=True, dtype=float, encoding="utf-8")
        cols = list(data.dtype.names or [])
        if not cols:
            raise ValueError("No header detected")

        def pick(primary: Optional[str], alts: Tuple[str, ...]) -> Optional[np.ndarray]:
            colset = set(cols)
            if primary and primary in colset:
                return np.asarray(data[primary], float)
            for a in alts:
                if a in colset:
                    return np.asarray(data[a], float)
            return None

        t = pick(time_col, ("t", "Time", "TIME", "seconds", "sec", "Secs", "s"))
        pv = pick(pv_col, ("pv", "PV", "y", "Y", "process", "Process", "feedback", "Feedback"))
        cv = None
        if cv_col is not None:
            cv = pick(cv_col, ("CO", "co", "cv", "CV", "u", "U", "command", "Command",
                               "control", "Control", "output", "Output", "CO%", "CV%"))

    except Exception:
        import pandas as pd
        df = pd.read_csv(path)
        cols = [c.strip() for c in df.columns]
        colmap = {c.strip(): c for c in df.columns}

        def pick(primary: Optional[str], alts: Tuple[str, ...]) -> Optional[np.ndarray]:
            if primary and primary in colmap:
                return df[colmap[primary]].to_numpy(dtype=float)
            for a in alts:
                if a in colmap:
                    return df[colmap[a]].to_numpy(dtype=float)
            return None

        t = pick(time_col, ("t", "Time", "TIME", "seconds", "sec", "Secs", "s"))
        pv = pick(pv_col, ("pv", "PV", "y", "Y", "process", "Process", "feedback", "Feedback"))
        cv = None
        if cv_col is not None:
            cv = pick(cv_col, ("CO", "co", "cv", "CV", "u", "U", "command", "Command",
                               "control", "Control", "output", "Output", "CO%", "CV%"))

    if t is None or pv is None:
        raise ValueError(f"CSV must include time and PV columns. Found columns: {cols}")

    t = np.asarray(t, float)
    pv = np.asarray(pv, float)

    if time_unit.lower() == "ms":
        t = t / 1000.0

    if cv is None:
        cv = np.zeros_like(pv, dtype=float)
    else:
        cv = np.asarray(cv, float)

    ok = np.isfinite(t) & np.isfinite(pv) & np.isfinite(cv)
    t = t[ok]
    pv = pv[ok]
    cv = cv[ok]

    if t.size < 5:
        raise ValueError("Not enough samples after cleaning.")

    dt = np.diff(t)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    dt_s = float(np.median(dt)) if dt.size else float((t[-1] - t[0]) / max(len(t) - 1, 1))

    return StepSeries(t=t, cv=cv, pv=pv, pv_raw=pv.copy(), dt_s=dt_s, source_path=path)


def smooth_moving_average(x: np.ndarray, win: int = 9) -> np.ndarray:
    win = int(max(1, win))
    if win == 1:
        return np.asarray(x, float).copy()
    x = np.asarray(x, float)
    pad = win // 2
    xp = np.pad(x, (pad, pad), mode="edge")
    k = np.ones(win, dtype=float) / float(win)
    return np.convolve(xp, k, mode="valid")


def _span_mean(x: np.ndarray, span: Tuple[int, int]) -> float:
    a, b = span
    a = max(int(a), 0)
    b = min(int(b), len(x))
    seg = x[a:b]
    seg = seg[np.isfinite(seg)]
    return float(np.mean(seg)) if seg.size else float("nan")


def _rmse(y: np.ndarray, yhat: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    if mask is None:
        e = y - yhat
        e = e[np.isfinite(e)]
    else:
        e = (y - yhat)[mask]
        e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e * e))) if e.size else float("nan")


def _mask_from_span(n: int, span: Optional[Tuple[int, int]]) -> Optional[np.ndarray]:
    if span is None:
        return None
    a, b = span
    a = max(int(a), 0)
    b = min(int(b), n)
    if b <= a:
        return None
    m = np.zeros(n, dtype=bool)
    m[a:b] = True
    return m


def auto_detect_step_index(ts: StepSeries) -> int:
    if np.nanmax(ts.cv) - np.nanmin(ts.cv) > 1e-9:
        d = np.diff(ts.cv)
        return max(0, min(int(np.argmax(np.abs(d))) + 1, len(ts.t) - 1))
    dp = np.diff(ts.pv)
    return max(0, min(int(np.argmax(np.abs(dp))) + 1, len(ts.t) - 1))


def auto_detect_deadtime_index(ts: StepSeries, selections: StepTuneSelections) -> Optional[int]:
    base = selections.baseline.as_tuple()
    if base is None:
        return None
    step_i = selections.t_step.get() or auto_detect_step_index(ts)

    pv = ts.pv
    dp = np.diff(pv)

    a, b = base
    a = max(int(a), 0)
    b = min(int(b), len(pv))
    if b - a < 6:
        return None

    dp_base = dp[a : max(a, b - 1)]
    dp_base = dp_base[np.isfinite(dp_base)]
    if dp_base.size < 5:
        return None

    sigma = float(np.std(dp_base, ddof=1))
    thr = max(5.0 * sigma, 1e-12)

    for k in range(max(int(step_i), 1), len(pv) - 1):
        if np.isfinite(dp[k]) and abs(dp[k]) >= thr:
            return k + 1
    return None


def simulate_fopdt_overlay(t: np.ndarray, *, pv0: float, du: float, K: float, tau: float, theta: float, t_step: float) -> np.ndarray:
    tau = max(float(tau), 1e-9)
    y = np.full_like(t, pv0, dtype=float)
    t_on = float(t_step + theta)
    idx = t >= t_on
    tt = t[idx] - t_on
    y[idx] = pv0 + (K * du) * (1.0 - np.exp(-tt / tau))
    return y


def simulate_ipdt_overlay(t: np.ndarray, *, pv0: float, du: float, K: float, theta: float, t_step: float) -> np.ndarray:
    y = np.full_like(t, pv0, dtype=float)
    t_on = float(t_step + theta)
    idx = t >= t_on
    tt = t[idx] - t_on
    y[idx] = pv0 + (K * du) * tt
    return y


def simulate_sopdt_underdamped_overlay(t: np.ndarray, *, pv0: float, du: float, K: float, zeta: float, wn: float, theta: float, t_step: float) -> np.ndarray:
    zeta = float(zeta)
    wn = max(float(wn), 1e-6)
    if zeta >= 1.0:
        zeta = 0.999
    wd = wn * np.sqrt(1.0 - zeta * zeta)
    phi = np.arctan2(np.sqrt(1.0 - zeta * zeta), zeta)

    y = np.full_like(t, pv0, dtype=float)
    t_on = float(t_step + theta)
    idx = t >= t_on
    tt = t[idx] - t_on
    y_unit = 1.0 - (np.exp(-zeta * wn * tt) / np.sqrt(1.0 - zeta * zeta)) * np.sin(wd * tt + phi)
    y[idx] = pv0 + (K * du) * y_unit
    return y


def compute_pid_gains(model: PVModelType, result: StepIdResult, *, method: TuningMethod = "IMC_PID", lam_s: float = 1.0) -> dict[str, float]:
    lam_s = float(max(lam_s, 1e-6))
    theta = float(max(result.theta_s, 0.0))

    if model == "FOPDT":
        K = float(result.get("K", 0.0) or 0.0)
        tau = float(result.get("tau_s", 0.0) or 0.0)
        tau = max(tau, 1e-6)
        if abs(K) < 1e-12:
            raise ValueError("Cannot tune: model gain K is ~0.")

        if method == "IMC_PI":
            Kp = tau / (K * (lam_s + theta))
            Ti = tau
            Ki = Kp / Ti
            return {"Kp": float(Kp), "Ki": float(Ki), "Kd": 0.0, "Ti": float(Ti), "Td": 0.0}

        # IMC_PID (default)
        Kp = (tau + 0.5 * theta) / (K * (lam_s + 0.5 * theta))
        Ti = tau + 0.5 * theta
        Td = (tau * theta) / (2.0 * tau + theta) if (2.0 * tau + theta) > 1e-12 else 0.0
        Ki = Kp / max(Ti, 1e-9)
        Kd = Kp * Td
        return {"Kp": float(Kp), "Ki": float(Ki), "Kd": float(Kd), "Ti": float(Ti), "Td": float(Td)}

    if model == "IPDT":
        K = float(result.get("K", 0.0) or 0.0)
        if abs(K) < 1e-12:
            raise ValueError("Cannot tune: IPDT slope gain K is ~0.")
        th = max(theta, 1e-6)
        # SIMC PI (safe starter)
        Kp = 1.0 / (K * th)
        Ti = 4.0 * th
        Ki = Kp / Ti
        return {"Kp": float(Kp), "Ki": float(Ki), "Kd": 0.0, "Ti": float(Ti), "Td": 0.0}

    if model == "SOPDT_UNDERDAMPED":
        K = float(result.get("K", 0.0) or 0.0)
        zeta = float(result.get("zeta", 0.0) or 0.0)
        wn = float(result.get("wn", 0.0) or 0.0)
        if abs(K) < 1e-12:
            raise ValueError("Cannot tune: model gain K is ~0.")
        if zeta <= 0 or wn <= 0:
            raise ValueError("Cannot tune: SOPDT needs zeta and wn.")
        tau_eff = 1.0 / max(zeta * wn, 1e-6)
        # Conservative PI using effective dominant time constant
        Kp = tau_eff / (K * (lam_s + theta))
        Ti = tau_eff
        Ki = Kp / Ti
        return {"Kp": float(Kp), "Ki": float(Ki), "Kd": 0.0, "Ti": float(Ti), "Td": 0.0}

    raise ValueError(f"Unknown model: {model}")


def identify(ts: StepSeries, selections: StepTuneSelections, model: PVModelType) -> tuple[StepIdResult, np.ndarray]:
    base = selections.baseline.as_tuple()
    if base is None:
        raise ValueError("Select a BASELINE span first.")

    final = selections.final.as_tuple()
    if model in ("FOPDT", "SOPDT_UNDERDAMPED") and final is None:
        raise ValueError("Select a FINAL span for this model.")

    step_i = selections.t_step.get()
    if step_i is None:
        step_i = auto_detect_step_index(ts)
        selections.t_step.set(step_i)
    t_step_s = float(ts.t[int(step_i)])

    cv0 = _span_mean(ts.cv, base)
    pv0 = _span_mean(ts.pv, base)

    cv1 = _span_mean(ts.cv, final) if final is not None else float(ts.cv[-1])
    pv1 = _span_mean(ts.pv, final) if final is not None else float(ts.pv[-1])

    du = float(cv1 - cv0)
    dy = float(pv1 - pv0)
    if abs(du) < 1e-12:
        raise ValueError("CV step size (du) is ~0. Check baseline/final spans or CSV CV/CO column.")

    theta_i = selections.theta.get()
    dead_i = selections.t_dead.get()

    if theta_i is None and dead_i is None:
        di = auto_detect_deadtime_index(ts, selections)
        if di is not None:
            selections.t_dead.set(di)
            dead_i = di

    theta_anchor_i = theta_i if theta_i is not None else dead_i
    theta_s = 0.0
    if theta_anchor_i is not None:
        theta_s = float(ts.t[int(theta_anchor_i)] - t_step_s)
        theta_s = max(theta_s, 0.0)

    fit_mask = _mask_from_span(len(ts.t), selections.fit.as_tuple())

    if model == "FOPDT":
        K = float(dy / du)
        t63_i = selections.t63.get()
        t_on = float(t_step_s + theta_s)
        tau_s = max(ts.dt_s, 1e-6)

        if t63_i is not None:
            tau_s = float(ts.t[int(t63_i)] - t_on)
            tau_s = max(tau_s, ts.dt_s)
        else:
            target = pv0 + 0.6321205588 * dy
            idx = np.where(ts.t >= t_on)[0]
            if idx.size:
                k0 = int(idx[0])
                kk = None
                for k in range(k0, len(ts.pv)):
                    if not np.isfinite(ts.pv[k]):
                        continue
                    if (dy >= 0 and ts.pv[k] >= target) or (dy < 0 and ts.pv[k] <= target):
                        kk = k
                        break
                if kk is not None:
                    tau_s = float(ts.t[int(kk)] - t_on)
                    tau_s = max(tau_s, ts.dt_s)

        pv_hat = simulate_fopdt_overlay(ts.t, pv0=pv0, du=du, K=K, tau=tau_s, theta=theta_s, t_step=t_step_s)
        res = StepIdResult(
            model="FOPDT",
            cv0=cv0, cv1=cv1, pv0=pv0, pv1=pv1, du=du, dy=dy,
            t_step_s=t_step_s, theta_s=theta_s,
            params={"K": float(K), "tau_s": float(tau_s)},
        )
        res.rmse = _rmse(ts.pv, pv_hat, mask=fit_mask)
        res.n_fit = int(np.sum(fit_mask)) if fit_mask is not None else int(len(ts.t))
        return res, pv_hat

    if model == "IPDT":
        ramp_span = selections.slope.as_tuple() or selections.fit.as_tuple() or selections.final.as_tuple()
        if ramp_span is None:
            raise ValueError("For IPDT, select a SLOPE span (preferred) or FIT span over the ramp region.")

        a, b = ramp_span
        a = max(int(a), 0)
        b = min(int(b), len(ts.t))

        tt = ts.t[a:b]
        yy = ts.pv[a:b]
        m = np.isfinite(tt) & np.isfinite(yy)
        tt = tt[m]
        yy = yy[m]
        if tt.size < 5:
            raise ValueError("Selected ramp span too small for IPDT slope fit.")

        A = np.vstack([tt, np.ones_like(tt)]).T
        slope, _ = np.linalg.lstsq(A, yy, rcond=None)[0]
        K = float(slope / du)

        pv_hat = simulate_ipdt_overlay(ts.t, pv0=pv0, du=du, K=K, theta=theta_s, t_step=t_step_s)
        res = StepIdResult(
            model="IPDT",
            cv0=cv0, cv1=cv1, pv0=pv0, pv1=pv1, du=du, dy=dy,
            t_step_s=t_step_s, theta_s=theta_s,
            params={"K": float(K)},
            note="IPDT fits slope on SLOPE/FIT span; PV does not settle.",
        )
        res.rmse = _rmse(ts.pv, pv_hat, mask=fit_mask)
        res.n_fit = int(np.sum(fit_mask)) if fit_mask is not None else int(len(ts.t))
        return res, pv_hat

    if model == "SOPDT_UNDERDAMPED":
        peak_i = selections.peak.get()
        if peak_i is None:
            raise ValueError("For SOPDT_UNDERDAMPED, click to set a PEAK point (first overshoot peak).")

        K = float(dy / du)

        t_peak = float(ts.t[int(peak_i)])
        pv_peak = float(ts.pv[int(peak_i)])

        Mp = float((pv_peak - pv1) / dy) if abs(dy) > 1e-12 else 0.0
        Mp = abs(Mp)
        if Mp <= 1e-6:
            raise ValueError("Peak overshoot too small; cannot identify underdamped parameters.")

        lnMp = np.log(Mp)
        zeta = float(-lnMp / np.sqrt(np.pi * np.pi + lnMp * lnMp))
        zeta = min(max(zeta, 0.01), 0.99)

        t_on = float(t_step_s + theta_s)
        Tp = float(t_peak - t_on)
        if Tp <= ts.dt_s:
            raise ValueError("Peak is too close to step/theta; check PEAK and THETA selections.")

        wd = float(2.0 * np.pi / Tp)
        wn = float(wd / np.sqrt(1.0 - zeta * zeta))

        pv_hat = simulate_sopdt_underdamped_overlay(ts.t, pv0=pv0, du=du, K=K, zeta=zeta, wn=wn, theta=theta_s, t_step=t_step_s)
        res = StepIdResult(
            model="SOPDT_UNDERDAMPED",
            cv0=cv0, cv1=cv1, pv0=pv0, pv1=pv1, du=du, dy=dy,
            t_step_s=t_step_s, theta_s=theta_s,
            params={"K": float(K), "zeta": float(zeta), "wn": float(wn)},
        )
        res.rmse = _rmse(ts.pv, pv_hat, mask=fit_mask)
        res.n_fit = int(np.sum(fit_mask)) if fit_mask is not None else int(len(ts.t))
        return res, pv_hat

    raise ValueError(f"Unknown model: {model}")
