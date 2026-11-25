"""The investment committee's analysts.

Each analyst looks at one aspect of a stock, scores what it sees and explains
why. A Point's weight is in [-1, 1]: positive is bullish, negative is bearish,
zero is a neutral observation. An analyst's score is the mean weight of the
points it could evaluate, so missing data lowers confidence instead of
silently counting as good or bad.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import indicators as ind

FINANCIAL_SECTORS = {"Financial Services", "Financials"}
SECTOR_CAP = 0.30  # max share of the portfolio in one sector


@dataclass
class Point:
    text: str
    weight: float
    topic: str


@dataclass
class Opinion:
    role: str
    persona: str
    score: float
    points: list[Point]
    coverage: float  # share of the analyst's metrics that had data
    extra: dict = field(default_factory=dict)

    @property
    def stance(self) -> str:
        if self.score >= 0.25:
            return "Bullish"
        if self.score >= 0.08:
            return "Mildly bullish"
        if self.score > -0.08:
            return "Neutral"
        if self.score > -0.25:
            return "Mildly bearish"
        return "Bearish"


@dataclass
class StockData:
    ticker: str
    name: str
    isin: str
    info: dict
    close: pd.Series  # native currency, adjusted
    bench: pd.Series  # benchmark closes (EUR)
    eur_rate: float  # EUR per 1 unit of quote currency
    news: list[dict] = field(default_factory=list)

    @property
    def currency(self) -> str:
        return self.info.get("currency") or "EUR"

    @property
    def price(self) -> float:
        return float(self.close.iloc[-1])

    @property
    def price_eur(self) -> float:
        return self.price * self.eur_rate

    @property
    def sector(self) -> str:
        return self.info.get("sector") or "Unknown"

    @property
    def is_financial(self) -> bool:
        return self.sector in FINANCIAL_SECTORS


@dataclass
class PortfolioContext:
    total_value_eur: float
    cash_eur: float
    sector_weights: dict[str, float]  # sector -> share of total value
    holdings: set[str]


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:+.{digits}f}%"


def mag(x: float, digits: int = 1) -> str:
    """Unsigned percentage, for sentences that already say 'above'/'below'."""
    return f"{abs(x) * 100:.{digits}f}%"


def _num(info: dict, key: str) -> float | None:
    v = info.get(key)
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v == v else None  # drop NaN


def _band(value: float, bands: list[tuple[float, float]], last: float) -> float:
    """bands = [(threshold, weight), ...]; first threshold the value exceeds wins."""
    for threshold, weight in bands:
        if value > threshold:
            return weight
    return last


def _finish(role, persona, points, expected, extra=None) -> Opinion:
    scored = [p for p in points if p.topic != "info"]
    score = sum(p.weight for p in scored) / max(len(scored), 1)
    score = max(-1.0, min(1.0, score))
    coverage = min(1.0, len(scored) / expected) if expected else 1.0
    return Opinion(role, persona, score, points, coverage, extra or {})


# ---------------------------------------------------------------- fundamentals
def fundamental(sd: StockData) -> Opinion:
    i, pts = sd.info, []
    rg = _num(i, "revenueGrowth")
    if rg is not None:
        w = _band(rg, [(0.20, 1.0), (0.10, 0.6), (0.03, 0.2), (-0.03, -0.2)], -0.7)
        word = "strong" if rg > 0.10 else "modest" if rg > 0.03 else "flat" if rg > -0.03 else "shrinking"
        verb = "growing" if rg >= 0 else "falling"
        pts.append(Point(f"Revenue is {verb} {mag(rg)} year over year ({word}).", w, "growth"))
    eg = _num(i, "earningsGrowth")
    if eg is not None:
        if eg > 1.0:
            # Triple-digit jumps are usually a depressed prior year (write-offs, one-offs), not real growth.
            pts.append(Point(f"Earnings jumped {pct(eg, 0)} versus a year ago, but that mostly reflects a depressed prior year.", 0.3, "growth"))
        else:
            w = _band(eg, [(0.25, 0.9), (0.10, 0.5), (0.0, 0.1), (-0.15, -0.4)], -0.8)
            pts.append(Point(f"Earnings changed {pct(eg)} versus a year ago.", w, "growth"))
    om = _num(i, "operatingMargins")
    if om is not None:
        w = _band(om, [(0.25, 0.7), (0.15, 0.4), (0.08, 0.1), (0.0, -0.2)], -0.7)
        pts.append(Point(f"Operating margin is {om * 100:.1f}%.", w, "profitability"))
    roe = _num(i, "returnOnEquity")
    if roe is not None:
        w = _band(roe, [(0.25, 0.6), (0.15, 0.4), (0.08, 0.1), (0.0, -0.2)], -0.6)
        pts.append(Point(f"Return on equity is {roe * 100:.1f}%.", w, "profitability"))
    if not sd.is_financial:
        de = _num(i, "debtToEquity")
        if de is not None:
            w = _band(-de, [(-50, 0.4), (-100, 0.1), (-200, -0.3)], -0.6)
            label = "conservative" if de < 50 else "moderate" if de < 100 else "heavy" if de < 200 else "very heavy"
            pts.append(Point(f"Debt/equity is {de:.0f}% ({label} leverage).", w, "balance"))
        cr = _num(i, "currentRatio")
        if cr is not None and cr < 1.0:
            pts.append(Point(f"Current ratio is {cr:.2f}, below 1 — short-term liabilities exceed liquid assets.", -0.2, "balance"))
        fcf, rev = _num(i, "freeCashflow"), _num(i, "totalRevenue")
        if fcf is not None and rev:
            m = fcf / rev
            w = _band(m, [(0.15, 0.5), (0.05, 0.2), (0.0, 0.0)], -0.6)
            pts.append(Point(f"Free-cash-flow margin is {m * 100:.1f}% of revenue.", w, "cashflow"))
    else:
        pts.append(Point("Financial company: leverage and cash-flow ratios are not comparable, so they are skipped.", 0, "info"))
    return _finish("Fundamental Analyst", "Fiona", pts, 6 if not sd.is_financial else 4)


# ------------------------------------------------------------------- valuation
def valuation(sd: StockData) -> Opinion:
    i, pts = sd.info, []
    eg = _num(i, "earningsGrowth") or 0.0
    fpe = _num(i, "forwardPE")
    pe = fpe if fpe is not None else _num(i, "trailingPE")
    label = "forward" if fpe is not None else "trailing"
    if pe is not None:
        if pe <= 0:
            pts.append(Point(f"The {label} P/E is negative — the company is not expected to be profitable.", -0.8, "valuation"))
        else:
            w = _band(-pe, [(-12, 0.7), (-18, 0.4), (-25, 0.1), (-35, -0.3), (-50, -0.6)], -0.9)
            note = ""
            if 0.25 < eg <= 1.0 and w < 0.4:
                w += 0.3
                note = " — rich, but partly justified by fast earnings growth"
            pts.append(Point(f"It trades at {pe:.1f}x {label} earnings{note}.", w, "valuation"))
    peg = _num(i, "trailingPegRatio") or _num(i, "pegRatio")
    if peg is not None and peg > 0:
        w = _band(-peg, [(-1.0, 0.6), (-1.5, 0.3), (-2.5, -0.1)], -0.5)
        pts.append(Point(f"PEG ratio is {peg:.2f} (price paid per unit of growth).", w, "valuation"))
    # ADRs (e.g. TSMC) quote in USD but report in their home currency; ratios that mix
    # the two are meaningless, so skip them.
    same_ccy = i.get("financialCurrency") in (None, i.get("currency"))
    if not sd.is_financial and same_ccy:
        ev = _num(i, "enterpriseToEbitda")
        if ev is not None and ev > 0:
            w = _band(-ev, [(-8, 0.5), (-14, 0.2), (-22, -0.1), (-35, -0.4)], -0.7)
            pts.append(Point(f"EV/EBITDA is {ev:.1f}x.", w, "valuation"))
        fcf, mcap = _num(i, "freeCashflow"), _num(i, "marketCap")
        if fcf is not None and mcap:
            y = fcf / mcap
            w = _band(y, [(0.06, 0.6), (0.04, 0.3), (0.02, 0.0), (0.0, -0.3)], -0.6)
            pts.append(Point(f"Free-cash-flow yield is {y * 100:.1f}%.", w, "valuation"))
    ps = _num(i, "priceToSalesTrailing12Months") if same_ccy else None
    if ps is not None:
        if ps > 20:
            pts.append(Point(f"Price/sales of {ps:.1f}x leaves no room for disappointment.", -0.6, "valuation"))
        elif ps > 10:
            pts.append(Point(f"Price/sales is a demanding {ps:.1f}x.", -0.3, "valuation"))
        elif ps < 1.5:
            pts.append(Point(f"Price/sales is only {ps:.1f}x.", 0.3, "valuation"))
    if sd.is_financial:
        pb = _num(i, "priceToBook")
        if pb is not None:
            w = _band(-pb, [(-1.0, 0.6), (-1.5, 0.3), (-2.5, 0.0)], -0.4)
            pts.append(Point(f"Price/book is {pb:.2f}x.", w, "valuation"))
    return _finish("Valuation Analyst", "Victor", pts, 4)


# ------------------------------------------------------------------ technicals
def technical(sd: StockData) -> Opinion:
    s, pts = sd.close.dropna(), []
    p = float(s.iloc[-1])
    s200, s50 = ind.sma(s, 200), ind.sma(s, 50)
    if s200:
        gap = p / s200 - 1
        w = _band(gap, [(0.15, 0.4), (0.0, 0.6), (-0.10, -0.4)], -0.7)
        if gap > 0.15:
            txt = f"Price is {mag(gap)} above its 200-day average: a strong uptrend, though stretched."
        elif gap > 0:
            txt = f"Price is {mag(gap)} above its 200-day average: the long-term trend is up."
        else:
            txt = f"Price is {mag(gap)} below its 200-day average: the long-term trend is down."
        pts.append(Point(txt, w, "trend"))
    if s50 and s200:
        if s50 > s200:
            pts.append(Point("The 50-day average is above the 200-day average (bullish alignment).", 0.4, "trend"))
        else:
            pts.append(Point("The 50-day average is below the 200-day average (bearish alignment).", -0.4, "trend"))
    r = ind.rsi(s)
    if r is not None:
        if r > 75:
            pts.append(Point(f"RSI(14) is {r:.0f}: overbought, a pullback is likely.", -0.5, "overbought"))
        elif r > 60:
            pts.append(Point(f"RSI(14) is {r:.0f}: healthy buying pressure.", 0.2, "trend"))
        elif r >= 40:
            pts.append(Point(f"RSI(14) is {r:.0f}: neutral.", 0.0, "trend"))
        elif r >= 30:
            pts.append(Point(f"RSI(14) is {r:.0f}: sellers in control.", -0.2, "trend"))
        else:
            pts.append(Point(f"RSI(14) is {r:.0f}: oversold, a bounce is possible.", 0.2, "oversold"))
    m = ind.macd_hist(s)
    if m is not None:
        now, before = m
        if now > 0 and now >= before:
            pts.append(Point("MACD is positive and rising: momentum is building.", 0.3, "trend"))
        elif now > 0:
            pts.append(Point("MACD is positive but fading.", 0.05, "trend"))
        elif now < before:
            pts.append(Point("MACD is negative and falling: momentum is deteriorating.", -0.3, "trend"))
        else:
            pts.append(Point("MACD is negative but improving.", -0.05, "trend"))
    fh = ind.from_high(s)
    if fh is not None:
        if fh > -0.05:
            pts.append(Point(f"It sits only {mag(fh)} below its 52-week high.", 0.2, "trend"))
        elif fh < -0.30:
            pts.append(Point(f"It is {mag(fh)} below its 52-week high.", -0.3, "trend"))
        else:
            pts.append(Point(f"It is {mag(fh)} below its 52-week high.", 0.0, "trend"))
    return _finish("Technical Analyst", "Tara", pts, 5, {"rsi": r})


# --------------------------------------------------------- sentiment / momentum
def sentiment(sd: StockData) -> Opinion:
    i, s, pts = sd.info, sd.close.dropna(), []
    n = _num(i, "numberOfAnalystOpinions") or 0
    rec = _num(i, "recommendationMean")
    if rec is not None and n >= 3:
        w = _band(-rec, [(-1.8, 0.6), (-2.3, 0.3), (-3.0, 0.0)], -0.5)
        key = (i.get("recommendationKey") or "").replace("_", " ")
        pts.append(Point(f"{int(n)} Wall Street analysts rate it {rec:.1f}/5 on average ({key}).", w, "sentiment"))
    tgt = _num(i, "targetMeanPrice")
    if tgt and n >= 3:
        up = tgt / sd.price - 1
        w = _band(up, [(0.25, 0.6), (0.10, 0.3), (0.0, 0.0)], -0.5)
        pts.append(Point(f"The average analyst price target implies {mag(up)} {'upside' if up >= 0 else 'downside'}.", w, "sentiment"))
    r6 = ind.ret(s, 126)
    # Compare in EUR: the stock's native-currency return adjusted to the EUR benchmark is close enough over 6 months.
    b6 = ind.ret(sd.bench.dropna(), 126)
    if r6 is not None and b6 is not None:
        rel = r6 - b6
        w = _band(rel, [(0.10, 0.5), (0.0, 0.2), (-0.10, -0.2)], -0.5)
        pts.append(Point(f"Over 6 months it returned {pct(r6)} versus {pct(b6)} for the MSCI World benchmark.", w, "momentum"))
    r1 = ind.ret(s, 21)
    if r1 is not None:
        if r1 > 0.15:
            pts.append(Point(f"It jumped {mag(r1)} in the last month — buying now risks chasing.", -0.2, "overbought"))
        elif r1 < -0.10:
            pts.append(Point(f"It fell {mag(r1)} in the last month.", -0.2, "momentum"))
        else:
            pts.append(Point(f"Last month: {pct(r1)}.", 0.0, "momentum"))
    sp = _num(i, "shortPercentOfFloat")
    if sp is not None and sp > 0.08:
        pts.append(Point(f"{sp * 100:.1f}% of the float is sold short — some investors are betting against it.", -0.4, "sentiment"))
    for item in sd.news[:4]:
        src = f" ({item['source']}, {item['date']})" if item.get("source") else ""
        pts.append(Point(f"Headline: “{item['title']}”{src}", 0, "info"))
    return _finish("Sentiment & Momentum Analyst", "Sam", pts, 4)


# ------------------------------------------------------------------------ risk
def risk(sd: StockData, pctx: PortfolioContext) -> Opinion:
    s, i, pts = sd.close.dropna(), sd.info, []
    vol = ind.ann_vol(s)
    if vol is not None:
        w = _band(-vol, [(-0.20, 0.4), (-0.30, 0.1), (-0.45, -0.3)], -0.7)
        pts.append(Point(f"Annualised volatility is {vol * 100:.0f}%.", w, "volatility"))
    dd = ind.max_drawdown(s)
    if dd is not None:
        w = _band(dd, [(-0.15, 0.3), (-0.30, 0.0), (-0.50, -0.4)], -0.7)
        pts.append(Point(f"Worst peak-to-trough fall in the past year: {mag(dd)}.", w, "drawdown"))
    b = _num(i, "beta") or ind.beta(s, sd.bench)
    if b is not None:
        if b > 1.6:
            pts.append(Point(f"Beta of {b:.2f}: it swings much harder than the market.", -0.3, "volatility"))
        elif b < 0.8:
            pts.append(Point(f"Beta of {b:.2f}: defensive, moves less than the market.", 0.2, "volatility"))
        else:
            pts.append(Point(f"Beta of {b:.2f}: moves roughly with the market.", 0.0, "volatility"))
    mcap = (_num(i, "marketCap") or 0) * sd.eur_rate
    if mcap and mcap < 10e9:
        pts.append(Point(f"Market cap is only €{mcap / 1e9:.1f}bn — smaller and less liquid.", -0.2, "size"))
    sector_w = pctx.sector_weights.get(sd.sector, 0.0)
    if sector_w > SECTOR_CAP - 0.10:
        pts.append(Point(f"The portfolio already has {sector_w * 100:.0f}% in {sd.sector} — adding more concentrates risk.", -0.6, "concentration"))
    elif sector_w > 0:
        pts.append(Point(f"The portfolio holds {sector_w * 100:.0f}% in {sd.sector}.", 0.0, "concentration"))
    else:
        pts.append(Point(f"No exposure to {sd.sector} yet — this would diversify the portfolio.", 0.2, "concentration"))

    # Position sizing: target ~15% of the portfolio for a stock with 30% volatility,
    # scaled inversely with volatility, capped at 25% and by the room left under the sector cap.
    v = vol or 0.35
    target = min(0.25, 0.15 * 0.30 / max(v, 0.12))
    target = max(0.0, min(target, SECTOR_CAP - sector_w))
    return _finish("Risk Manager", "Rita", pts, 4, {"vol": vol, "max_weight": target, "sector_weight": sector_w})
