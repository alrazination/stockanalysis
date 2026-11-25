"""Glue between market data, the committee and the portfolio."""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from . import analysts as A
from . import committee, market
from . import portfolio as P
from .universe import BENCHMARK, UNIVERSE, lookup

ROOT = Path(__file__).resolve().parent.parent
DISCUSSIONS = ROOT / "discussions"

CASH_RESERVE = 0.05  # keep 5% in cash
MAX_PER_SECTOR_NEW = 1  # spread each round of buys across sectors


def _series(closes: pd.DataFrame, t: str) -> pd.Series:
    return closes[t].dropna() if t in closes else pd.Series(dtype=float)


def load_stocks(tickers: list[str], with_news: bool = True) -> tuple[dict[str, A.StockData], pd.Series]:
    closes = market.get_closes(tickers + [BENCHMARK[0]], period="2y")
    bench = _series(closes, BENCHMARK[0])
    with ThreadPoolExecutor(max_workers=6) as ex:
        infos = dict(zip(tickers, ex.map(market.get_info, tickers)))
        news = dict(zip(tickers, ex.map(market.get_news, tickers))) if with_news else {}
    out = {}
    for t in tickers:
        s, info = _series(closes, t), infos.get(t) or {}
        if len(s) < 60 or not info:
            continue  # not enough data to judge
        meta = lookup(t)
        out[t] = A.StockData(
            ticker=t,
            name=meta["name"] if meta["name"] != t else info.get("shortName", t),
            isin=meta["isin"],
            info=info,
            close=s,
            bench=bench,
            eur_rate=market.eur_per(info.get("currency")),
            news=news.get(t, []),
        )
    return out, bench


def portfolio_context(pf: dict, prices_eur: dict[str, float]) -> A.PortfolioContext:
    return A.PortfolioContext(
        total_value_eur=P.value(pf, prices_eur),
        cash_eur=pf["cash"],
        sector_weights=P.sector_weights(pf, prices_eur),
        holdings=set(pf["positions"]),
    )


def holding_prices_eur(pf: dict, stocks: dict[str, A.StockData] | None = None) -> dict[str, float]:
    stocks = stocks or {}
    out = {t: sd.price_eur for t, sd in stocks.items() if t in pf["positions"]}
    missing = [t for t in pf["positions"] if t not in out]
    if missing:
        closes = market.get_closes(missing, period="5d")
        for t in missing:
            s = _series(closes, t)
            if s.size:
                out[t] = float(s.iloc[-1]) * market.eur_per(market.get_info(t).get("currency"))
    return out


def bench_price() -> float | None:
    s = _series(market.get_closes([BENCHMARK[0]], period="5d"), BENCHMARK[0])
    return float(s.iloc[-1]) if s.size else None


def write_transcript(d: committee.Decision) -> str:
    folder = DISCUSSIONS / dt.date.today().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{d.ticker.replace('.', '_')}.md"
    path.write_text(d.transcript)
    return str(path.relative_to(ROOT))


# --------------------------------------------------------------------- flows
def analyze(pf: dict, ticker: str) -> committee.Decision | None:
    t = ticker.upper()
    stocks, _ = load_stocks([t])
    if t not in stocks:
        return None
    prices = holding_prices_eur(pf, stocks)
    ctx = portfolio_context(pf, prices)
    d = committee.run(stocks[t], ctx, held=pf["positions"].get(t))
    d.extra["file"] = write_transcript(d)
    return d


def scan(pf: dict, max_new: int = 6, write_top: int = 8, progress=print) -> tuple[list[committee.Decision], list[dict]]:
    """Analyse the whole universe and propose buys that fit the cash and risk rules."""
    tickers = [u[0] for u in UNIVERSE]
    progress(f"Fetching data for {len(tickers)} stocks (cached for the day)...")
    stocks, _ = load_stocks(tickers)
    prices = holding_prices_eur(pf, stocks)
    ctx = portfolio_context(pf, prices)
    progress(f"Committee is discussing {len(stocks)} stocks...")
    decisions = [committee.run(sd, ctx, held=pf["positions"].get(t)) for t, sd in stocks.items()]
    decisions.sort(key=lambda d: d.composite, reverse=True)

    total = ctx.total_value_eur
    budget = pf["cash"] - CASH_RESERVE * total
    sector_w = dict(ctx.sector_weights)
    per_sector: dict[str, int] = {}
    proposals: list[dict] = []
    for d in decisions:
        if len(proposals) >= max_new or budget < P.MIN_ORDER_EUR + P.FEE_EUR:
            break
        if not d.wants_buy or per_sector.get(d.sector, 0) >= MAX_PER_SECTOR_NEW:
            continue
        room = max(0.0, A.SECTOR_CAP - sector_w.get(d.sector, 0.0))
        weight = min(d.max_weight, room) * (1.0 if d.verdict == "STRONG BUY" else 0.75)
        amount = min(weight * total, budget - P.FEE_EUR)
        amount = float(int(amount // 5 * 5))
        if amount < P.MIN_ORDER_EUR:
            continue
        d.extra["file"] = write_transcript(d)
        sd = stocks[d.ticker]
        proposals.append(
            {
                "action": "BUY", "ticker": d.ticker, "name": d.name, "isin": sd.isin, "sector": d.sector,
                "amount_eur": amount, "price_eur": round(d.price_eur, 4), "verdict": d.verdict,
                "score": round(d.composite, 3), "conviction": d.conviction, "discussion": d.extra["file"],
            }
        )
        budget -= amount + P.FEE_EUR
        sector_w[d.sector] = sector_w.get(d.sector, 0) + amount / total
        per_sector[d.sector] = per_sector.get(d.sector, 0) + 1

    # Also keep transcripts for the next-best names so the reasoning is visible.
    for d in decisions[:write_top]:
        if "file" not in d.extra:
            d.extra["file"] = write_transcript(d)
    return decisions, proposals


def review(pf: dict) -> tuple[list[committee.Decision], list[dict]]:
    """Re-run the committee on every holding and propose sells where warranted."""
    tickers = list(pf["positions"])
    if not tickers:
        return [], []
    stocks, _ = load_stocks(tickers)
    prices = holding_prices_eur(pf, stocks)
    ctx = portfolio_context(pf, prices)
    decisions, proposals = [], []
    for t, sd in stocks.items():
        d = committee.run(sd, ctx, held=pf["positions"][t])
        d.extra["file"] = write_transcript(d)
        decisions.append(d)
        if d.wants_sell:
            shares = pf["positions"][t]["shares"] * (0.5 if d.verdict == "TRIM" else 1.0)
            proposals.append(
                {
                    "action": "SELL", "ticker": t, "name": d.name, "shares": round(shares, 6),
                    "price_eur": round(d.price_eur, 4), "verdict": d.verdict, "score": round(d.composite, 3),
                    "conviction": d.conviction, "discussion": d.extra["file"],
                }
            )
    return decisions, proposals


def execute(pf: dict, prop: dict) -> dict:
    """Execute a proposal at the fresh market price."""
    t = prop["ticker"]
    px = market.last_prices([t]).get(t)
    if px is None:
        raise RuntimeError(f"Could not fetch a live price for {t}.")
    price_eur = px * market.eur_per(market.get_info(t).get("currency"))
    if prop["action"] == "BUY":
        amount = min(prop["amount_eur"], pf["cash"] - P.FEE_EUR)
        tx = P.buy(pf, t, prop, amount, price_eur)
    else:
        tx = P.sell(pf, t, prop.get("shares"), price_eur)
    prop["status"] = "executed"
    prop["executed"] = P.now()
    prop["exec_price_eur"] = round(price_eur, 4)
    return tx
