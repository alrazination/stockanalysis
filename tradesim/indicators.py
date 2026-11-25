"""Small, dependency-free technical indicators on a pandas Series of closes."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> float | None:
    return float(s.iloc[-n:].mean()) if len(s) >= n else None


def rsi(s: pd.Series, n: int = 14) -> float | None:
    if len(s) < n + 1:
        return None
    d = s.diff().dropna()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    if dn.iloc[-1] == 0:
        return 100.0
    rs = up.iloc[-1] / dn.iloc[-1]
    return float(100 - 100 / (1 + rs))


def macd_hist(s: pd.Series) -> tuple[float, float] | None:
    """Return (histogram now, histogram 5 days ago) normalised by price."""
    if len(s) < 40:
        return None
    macd = s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean()
    hist = (macd - macd.ewm(span=9, adjust=False).mean()) / s
    return float(hist.iloc[-1]), float(hist.iloc[-6])


def ret(s: pd.Series, days: int) -> float | None:
    if len(s) <= days:
        return None
    return float(s.iloc[-1] / s.iloc[-1 - days] - 1)


def ann_vol(s: pd.Series, days: int = 252) -> float | None:
    r = s.iloc[-days - 1 :].pct_change().dropna()
    if len(r) < 60:
        return None
    return float(r.std() * math.sqrt(252))


def max_drawdown(s: pd.Series, days: int = 252) -> float | None:
    w = s.iloc[-days:]
    if len(w) < 60:
        return None
    return float((w / w.cummax() - 1).min())


def from_high(s: pd.Series, days: int = 252) -> float | None:
    w = s.iloc[-days:]
    if w.empty:
        return None
    return float(w.iloc[-1] / w.max() - 1)


def beta(s: pd.Series, bench: pd.Series, days: int = 252) -> float | None:
    df = pd.concat([s, bench], axis=1, join="inner").iloc[-days - 1 :].pct_change().dropna()
    if len(df) < 60:
        return None
    cov = np.cov(df.iloc[:, 0], df.iloc[:, 1])
    return float(cov[0, 1] / cov[1, 1]) if cov[1, 1] else None
