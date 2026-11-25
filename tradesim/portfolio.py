"""Paper-money portfolio: cash, positions, a trade ledger and pending proposals.

State lives in data/portfolio.json so every change is visible in git history.
Rules mirror Trade Republic: EUR account, €1 fee per order, fractional shares.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "portfolio.json"

FEE_EUR = 1.0
MIN_ORDER_EUR = 100.0  # keeps the €1 fee at or below 1% of each order
PROPOSAL_MAX_AGE_DAYS = 5


def now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def empty() -> dict:
    return {
        "currency": "EUR",
        "created": now(),
        "cash": 0.0,
        "deposits": [],  # {date, amount, bench_price}
        "positions": {},  # ticker -> {name, isin, sector, shares, avg_cost_eur, opened}
        "transactions": [],  # {date, type, ticker, shares, price_eur, amount_eur, fee, realized_pnl}
        "proposals": [],  # {id, date, action, ticker, ..., status}
        "snapshots": [],  # {date, value, cash, invested, bench_value}
    }


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return empty()


def save(pf: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(pf, indent=2, ensure_ascii=False) + "\n")


def deposit(pf: dict, amount: float, bench_price: float | None) -> None:
    if amount <= 0:
        raise ValueError("Deposit must be positive.")
    pf["cash"] = round(pf["cash"] + amount, 2)
    pf["deposits"].append({"date": now(), "amount": amount, "bench_price": bench_price})
    pf["transactions"].append({"date": now(), "type": "DEPOSIT", "amount_eur": amount})


def buy(pf: dict, ticker: str, meta: dict, eur_amount: float, price_eur: float) -> dict:
    if eur_amount < MIN_ORDER_EUR:
        raise ValueError(f"Order of €{eur_amount:.2f} is below the €{MIN_ORDER_EUR:.0f} minimum.")
    if eur_amount + FEE_EUR > pf["cash"] + 1e-9:
        raise ValueError(f"Not enough cash: need €{eur_amount + FEE_EUR:.2f}, have €{pf['cash']:.2f}.")
    shares = round(eur_amount / price_eur, 6)
    cost = shares * price_eur
    pos = pf["positions"].get(ticker)
    if pos:
        total = pos["shares"] + shares
        pos["avg_cost_eur"] = (pos["shares"] * pos["avg_cost_eur"] + cost + FEE_EUR) / total
        pos["shares"] = round(total, 6)
    else:
        pf["positions"][ticker] = {
            "name": meta.get("name", ticker),
            "isin": meta.get("isin", "?"),
            "sector": meta.get("sector", "Unknown"),
            "shares": shares,
            # Fee is folded into cost basis so P&L is honest.
            "avg_cost_eur": (cost + FEE_EUR) / shares,
            "opened": now(),
        }
    pf["cash"] = round(pf["cash"] - cost - FEE_EUR, 2)
    tx = {
        "date": now(), "type": "BUY", "ticker": ticker, "shares": shares,
        "price_eur": round(price_eur, 4), "amount_eur": round(cost, 2), "fee": FEE_EUR,
    }
    pf["transactions"].append(tx)
    return tx


def sell(pf: dict, ticker: str, shares: float | None, price_eur: float) -> dict:
    pos = pf["positions"].get(ticker)
    if not pos:
        raise ValueError(f"No position in {ticker}.")
    shares = pos["shares"] if shares is None or shares >= pos["shares"] - 1e-6 else shares
    proceeds = shares * price_eur
    realized = proceeds - FEE_EUR - shares * pos["avg_cost_eur"]
    pos["shares"] = round(pos["shares"] - shares, 6)
    if pos["shares"] <= 1e-6:
        del pf["positions"][ticker]
    pf["cash"] = round(pf["cash"] + proceeds - FEE_EUR, 2)
    tx = {
        "date": now(), "type": "SELL", "ticker": ticker, "shares": round(shares, 6),
        "price_eur": round(price_eur, 4), "amount_eur": round(proceeds, 2), "fee": FEE_EUR,
        "realized_pnl": round(realized, 2),
    }
    pf["transactions"].append(tx)
    return tx


def value(pf: dict, prices_eur: dict[str, float]) -> float:
    return pf["cash"] + sum(p["shares"] * prices_eur.get(t, p["avg_cost_eur"]) for t, p in pf["positions"].items())


def sector_weights(pf: dict, prices_eur: dict[str, float]) -> dict[str, float]:
    total = value(pf, prices_eur) or 1.0
    out: dict[str, float] = {}
    for t, p in pf["positions"].items():
        out[p["sector"]] = out.get(p["sector"], 0) + p["shares"] * prices_eur.get(t, p["avg_cost_eur"]) / total
    return out


def invested(pf: dict) -> float:
    return sum(d["amount"] for d in pf["deposits"])


def bench_value(pf: dict, bench_now: float | None) -> float | None:
    """What the deposits would be worth had they gone into the MSCI World ETF instead."""
    if not bench_now:
        return None
    total = 0.0
    for d in pf["deposits"]:
        if not d.get("bench_price"):
            return None
        total += d["amount"] * bench_now / d["bench_price"]
    return total


def snapshot(pf: dict, prices_eur: dict[str, float], bench_now: float | None) -> dict:
    snap = {
        "date": dt.date.today().isoformat(),
        "value": round(value(pf, prices_eur), 2),
        "cash": round(pf["cash"], 2),
        "invested": round(invested(pf), 2),
        "bench_value": round(bv, 2) if (bv := bench_value(pf, bench_now)) else None,
    }
    pf["snapshots"] = [s for s in pf["snapshots"] if s["date"] != snap["date"]] + [snap]
    return snap


# ------------------------------------------------------------------ proposals
def add_proposal(pf: dict, prop: dict) -> dict:
    n = len(pf["proposals"]) + 1
    prop = {"id": f"P{n:03d}", "date": now(), "status": "pending", **prop}
    pf["proposals"].append(prop)
    return prop


def pending(pf: dict) -> list[dict]:
    cutoff = dt.datetime.now() - dt.timedelta(days=PROPOSAL_MAX_AGE_DAYS)
    out = []
    for p in pf["proposals"]:
        if p["status"] != "pending":
            continue
        if dt.datetime.fromisoformat(p["date"]) < cutoff:
            p["status"] = "expired"
            continue
        out.append(p)
    return out
