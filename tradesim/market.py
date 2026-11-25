"""Market data access (Yahoo Finance via yfinance) with a per-day disk cache."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache"


def _yf():
    import yfinance as yf  # imported lazily so offline tests don't need network

    return yf


def _today() -> str:
    return dt.date.today().isoformat()


def _cache_file(kind: str, key: str, ext: str = "json") -> Path:
    safe = key.replace("/", "_").replace("^", "_").replace("=", "_")
    return CACHE / _today() / f"{kind}_{safe}.{ext}"


def _retry(fn, attempts: int = 3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # network hiccups / rate limits
            last = exc
            time.sleep(1.5 * (i + 1))
    raise last  # type: ignore[misc]


# --------------------------------------------------------------------------- info
def get_info(ticker: str, refresh: bool = False) -> dict:
    path = _cache_file("info", ticker)
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    try:
        info = _retry(lambda: _yf().Ticker(ticker).info) or {}
    except Exception:
        info = {}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, default=str))
    return info


def get_news(ticker: str, limit: int = 6) -> list[dict]:
    path = _cache_file("news", ticker)
    if path.exists():
        return json.loads(path.read_text())
    out: list[dict] = []
    try:
        raw = _retry(lambda: _yf().Ticker(ticker).news) or []
        for item in raw[:limit]:
            c = item.get("content", item)
            title = c.get("title")
            if not title:
                continue
            provider = c.get("provider", {})
            out.append(
                {
                    "title": title,
                    "date": (c.get("pubDate") or "")[:10],
                    "source": provider.get("displayName") if isinstance(provider, dict) else c.get("publisher"),
                }
            )
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


# ------------------------------------------------------------------------ prices
def get_closes(tickers: list[str], period: str = "2y", refresh: bool = False) -> pd.DataFrame:
    """Adjusted daily closes, one column per ticker (native currency)."""
    key = period + "_" + hashlib.md5(",".join(sorted(tickers)).encode()).hexdigest()[:10]
    path = _cache_file("closes", key, "csv")
    if path.exists() and not refresh:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df
    df = _retry(
        lambda: _yf().download(
            tickers, period=period, interval="1d", auto_adjust=True, progress=False, threads=True
        )
    )
    close = df["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    close.index = pd.to_datetime(close.index).tz_localize(None) if close.index.tz is not None else close.index
    close = close.sort_index()
    path.parent.mkdir(parents=True, exist_ok=True)
    close.to_csv(path)
    return close


def last_prices(tickers: list[str]) -> dict[str, float]:
    """Fresh (uncached) latest prices in native currency, used for executing trades."""
    df = get_closes(tickers, period="5d", refresh=True)
    out = {}
    for t in tickers:
        if t in df and df[t].dropna().size:
            out[t] = float(df[t].dropna().iloc[-1])
    return out


# --------------------------------------------------------------------------- FX
_FX: dict[str, float] = {}


def eur_per(currency: str | None) -> float:
    """How many EUR one unit of `currency` is worth."""
    if not currency or currency.upper() == "EUR":
        return 1.0
    if currency == "GBp":  # London quotes in pence
        return eur_per("GBP") / 100.0
    cur = currency.upper()
    if cur in _FX:
        return _FX[cur]
    path = _cache_file("fx", cur)
    if path.exists():
        _FX[cur] = json.loads(path.read_text())["rate"]
        return _FX[cur]
    df = get_closes([f"EUR{cur}=X"], period="5d", refresh=True)
    per_eur = float(df.iloc[:, 0].dropna().iloc[-1])  # units of `cur` per 1 EUR
    rate = 1.0 / per_eur
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rate": rate}))
    _FX[cur] = rate
    return rate
