"""Export the simulator's state as web/data.json for the Trading Arena page."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from . import engine, market
from . import portfolio as P
from .universe import BENCHMARK

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data.json"


def _discussion(path: str | None) -> dict | None:
    if not path:
        return None
    js = (ROOT / path).with_suffix(".json")
    return json.loads(js.read_text()) if js.exists() else None


def _history(pf: dict, closes: pd.DataFrame, rates: dict[str, float]) -> list[dict]:
    """Daily portfolio and benchmark value since the first deposit, rebuilt from the ledger.

    Positions are valued with today's FX rate for non-EUR stocks (an approximation)."""
    if not pf["deposits"]:
        return []
    start = pd.Timestamp(pf["deposits"][0]["date"][:10])
    bench = closes[BENCHMARK[0]].dropna() if BENCHMARK[0] in closes else pd.Series(dtype=float)
    days = [d for d in closes.index if d >= start] or [start]
    txs = sorted(pf["transactions"], key=lambda t: t["date"])
    out = []
    for day in days:
        cash, shares, bench_units = 0.0, {}, 0.0
        for t in txs:
            if pd.Timestamp(t["date"][:10]) > day:
                break
            if t["type"] == "DEPOSIT":
                cash += t["amount_eur"]
            elif t["type"] == "BUY":
                cash -= t["amount_eur"] + t["fee"]
                shares[t["ticker"]] = shares.get(t["ticker"], 0) + t["shares"]
            elif t["type"] == "SELL":
                cash += t["amount_eur"] - t["fee"]
                shares[t["ticker"]] = shares.get(t["ticker"], 0) - t["shares"]
        for d in pf["deposits"]:
            if pd.Timestamp(d["date"][:10]) <= day and d.get("bench_price"):
                bench_units += d["amount"] / d["bench_price"]
        val = cash
        for tk, n in shares.items():
            s = closes[tk].loc[:day].dropna() if tk in closes else pd.Series(dtype=float)
            val += n * (float(s.iloc[-1]) * rates.get(tk, 1.0) if s.size else 0.0)
        b = bench.loc[:day]
        out.append({
            "date": day.date().isoformat(),
            "value": round(val, 2),
            "bench": round(bench_units * float(b.iloc[-1]), 2) if b.size and bench_units else None,
        })
    return out


def export() -> Path:
    pf = P.load()
    held = list(pf["positions"])
    traded = sorted({t["ticker"] for t in pf["transactions"] if t.get("ticker")})
    tickers = sorted(set(held) | set(traded))
    closes = market.get_closes(tickers + [BENCHMARK[0]], period="1y")
    rates = {t: market.eur_per(market.get_info(t).get("currency")) for t in tickers}
    prices = {t: float(closes[t].dropna().iloc[-1]) * rates[t] for t in held if t in closes}
    bench_now = engine.bench_price()
    total = P.value(pf, prices)
    inv = P.invested(pf)
    bv = P.bench_value(pf, bench_now)

    positions = []
    for t, p in pf["positions"].items():
        px = prices.get(t, p["avg_cost_eur"])
        val = p["shares"] * px
        spark = (closes[t].dropna().iloc[-60:] * rates[t]).round(2).tolist() if t in closes else []
        positions.append({
            "ticker": t, "name": p["name"], "sector": p["sector"], "shares": p["shares"],
            "avg_cost": round(p["avg_cost_eur"], 4), "price": round(px, 4), "value": round(val, 2),
            "pnl": round(val - p["shares"] * p["avg_cost_eur"], 2), "pnl_pct": round(px / p["avg_cost_eur"] - 1, 4),
            "weight": round(val / total, 4) if total else 0, "opened": p["opened"][:10], "spark": spark,
        })
    positions.sort(key=lambda r: -r["value"])

    P.pending(pf)  # marks stale proposals as expired
    recent = sorted(pf["proposals"], key=lambda p: p["date"], reverse=True)[:24]
    proposals = [{**p, "debate": _discussion(p.get("discussion"))} for p in recent]

    ranking_file = engine.RANKING
    ranking = json.loads(ranking_file.read_text())[:15] if ranking_file.exists() else []

    data = {
        "generated": P.now(),
        "start": pf["deposits"][0]["date"][:10] if pf["deposits"] else None,
        "summary": {
            "value": round(total, 2), "invested": round(inv, 2), "cash": round(pf["cash"], 2),
            "bench_value": round(bv, 2) if bv else None,
        },
        "history": _history(pf, closes, rates),
        "positions": positions,
        "proposals": proposals,
        "ranking": ranking,
        "transactions": list(reversed(pf["transactions"]))[:40],
        "reports": sorted(p.stem for p in (ROOT / "reports").glob("*.md")),
        "fx_note": "Non-EUR prices are converted to EUR at the latest Yahoo Finance FX rate.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    P.save(pf)
    return OUT


if __name__ == "__main__":
    print(export())
