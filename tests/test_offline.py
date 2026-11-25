"""Offline tests: synthetic data, no network."""

import numpy as np
import pandas as pd

from tradesim import analysts as A
from tradesim import committee
from tradesim import portfolio as P


def _series(drift, n=400, vol=0.01, seed=1):
    rng = np.random.default_rng(seed)
    r = drift + vol * rng.standard_normal(n)
    idx = pd.bdate_range(end="2026-11-25", periods=n)
    return pd.Series(100 * np.exp(np.cumsum(r)), index=idx)


GOOD = {
    "currency": "EUR", "sector": "Technology", "revenueGrowth": 0.25, "earningsGrowth": 0.3,
    "operatingMargins": 0.3, "returnOnEquity": 0.3, "debtToEquity": 20, "freeCashflow": 3e9,
    "totalRevenue": 1e10, "forwardPE": 15, "trailingPegRatio": 0.8, "enterpriseToEbitda": 10,
    "marketCap": 5e10, "recommendationMean": 1.6, "numberOfAnalystOpinions": 20, "targetMeanPrice": 999,
}
BAD = {
    "currency": "EUR", "sector": "Consumer Cyclical", "revenueGrowth": -0.1, "earningsGrowth": -0.4,
    "operatingMargins": -0.05, "returnOnEquity": -0.1, "debtToEquity": 300, "freeCashflow": -1e9,
    "totalRevenue": 1e10, "forwardPE": -5, "enterpriseToEbitda": 60, "marketCap": 5e9,
    "recommendationMean": 3.5, "numberOfAnalystOpinions": 10, "targetMeanPrice": 1,
}
CTX = A.PortfolioContext(2000, 2000, {}, set())


def _sd(info, close):
    return A.StockData("TST", "Test Co", "XX0000000000", info, close, _series(0.0003, seed=9), 1.0)


def test_good_stock_is_a_buy():
    d = committee.run(_sd(GOOD, _series(0.002)), CTX)
    assert d.verdict in ("BUY", "STRONG BUY"), d.composite
    assert "Round 4" in d.transcript and "Bull vs. Bear" in d.transcript


def test_bad_stock_is_not_bought():
    d = committee.run(_sd(BAD, _series(-0.002)), CTX)
    assert d.verdict in ("SELL", "STRONG SELL"), d.composite
    assert not d.wants_buy


def test_stop_loss_on_holding():
    held = {"shares": 10, "avg_cost_eur": 1000.0}
    d = committee.run(_sd(GOOD, _series(-0.002)), CTX, held=held)
    assert d.verdict == "SELL" and d.wants_sell


def test_portfolio_round_trip_with_fees():
    pf = P.empty()
    P.deposit(pf, 2000, 100.0)
    P.buy(pf, "TST", {"name": "Test", "sector": "Tech"}, 500, 50.0)
    assert pf["cash"] == 1499.0
    tx = P.sell(pf, "TST", None, 55.0)
    assert "TST" not in pf["positions"]
    assert abs(tx["realized_pnl"] - (550 - 1 - 501)) < 1e-6
    assert pf["cash"] == 2048.0
