"""The investment committee: four rounds of discussion ending in a verdict.

Round 1  Opening statements   – each analyst presents findings and a score.
Round 2  Bull vs. Bear        – the strongest arguments on each side, with rebuttals.
Round 3  Risk review          – volatility, concentration, position size, veto.
Round 4  Chair's verdict      – weighted vote, conviction, concrete order proposal.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from . import analysts as A

WEIGHTS = {
    "Fundamental Analyst": 0.30,
    "Valuation Analyst": 0.25,
    "Technical Analyst": 0.20,
    "Sentiment & Momentum Analyst": 0.15,
    "Risk Manager": 0.10,
}

LEVELS = ["STRONG SELL", "SELL", "HOLD", "BUY", "STRONG BUY"]

STOP_LOSS = -0.15  # sell if down 15% from average cost and the trend is broken
TAKE_PROFIT = 0.40  # trim half if up 40% and overbought


@dataclass
class Decision:
    ticker: str
    name: str
    verdict: str  # BUY / STRONG BUY / HOLD / SELL / STRONG SELL / TRIM
    composite: float
    conviction: str
    opinions: list[A.Opinion]
    debate: list[tuple[str, str]]
    risk_notes: list[str]
    chair_notes: list[str]
    max_weight: float
    price_eur: float
    sector: str
    held: dict | None = None
    transcript: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def wants_buy(self) -> bool:
        return self.verdict in ("BUY", "STRONG BUY") and not self.held

    @property
    def wants_sell(self) -> bool:
        return bool(self.held) and self.verdict in ("SELL", "STRONG SELL", "TRIM")


# --------------------------------------------------------------- debate helpers
GROWTHY = {"growth", "profitability", "cashflow"}


def _q(p: A.Point) -> str:
    return p.text.rstrip(".")


def _lq(p: A.Point) -> str:
    """Quote a point mid-sentence: lower-case the first word unless it is an acronym."""
    t = _q(p)
    return t[0].lower() + t[1:] if len(t) > 1 and t[1].islower() else t


def _find(points: list[A.Point], topics: set[str]) -> A.Point | None:
    """Only arguments with real weight (|w| >= 0.3) are used as counter-evidence."""
    return next((p for p in points if p.topic in topics and abs(p.weight) >= 0.3), None)


def _bull_rebuttal(bear: A.Point, bulls: list[A.Point]) -> str:
    t = bear.topic
    if t == "valuation" and (g := _find(bulls, {"growth"})):
        return f"It isn't cheap, I grant you. But {_lq(g)}. Paying up for that kind of growth is how you own compounders."
    if t in {"trend", "momentum", "overbought"} and (f := _find(bulls, GROWTHY)):
        return f"Price action is noise over a few weeks; the business is what we own — {_lq(f)}. Weakness can be an entry point."
    if t in {"volatility", "drawdown", "size"}:
        return "That is exactly what position sizing is for. Rita will cap the stake, and we can live with the swings."
    if t == "balance" and (c := _find(bulls, {"cashflow"})):
        return f"The cash generation covers it: {_lq(c)}."
    if t == "growth" and (v := _find(bulls, {"valuation"})):
        return f"Slow growth is already in the price: {_lq(v)}."
    if t == "sentiment" and (f := _find(bulls, GROWTHY | {"valuation"})):
        return f"Consensus is often late. The numbers speak for themselves: {_lq(f)}."
    return "Fair point. I can't fully argue that away — it is a real risk we should size for."


def _bear_rebuttal(bull: A.Point, bears: list[A.Point]) -> str:
    t = bull.topic
    if t in {"growth", "profitability"} and (v := _find(bears, {"valuation"})):
        return f"And the market knows that. It's priced in: {_lq(v)}."
    if t in {"trend", "momentum"} and (o := _find(bears, {"overbought", "valuation"})):
        return f"Trends end. {_q(o)} — late buyers get hurt first."
    if t == "valuation" and (g := _find(bears, {"growth"})):
        return f"Cheap stocks can stay cheap. {_q(g)} — this may be a value trap."
    if t in {"profitability", "cashflow"} and (tr := _find(bears, {"trend"})):
        return f"Then why is the market selling? {_q(tr)}."
    if t == "sentiment" and (v := _find(bears, {"valuation", "overbought"})):
        return f"When everyone already loves a stock, who is left to buy? {_q(v)}."
    return "I'll concede that one."


# --------------------------------------------------------------------- run
def run(sd: A.StockData, pctx: A.PortfolioContext, held: dict | None = None) -> Decision:
    ops = [
        A.fundamental(sd),
        A.valuation(sd),
        A.technical(sd),
        A.sentiment(sd),
        A.risk(sd, pctx),
    ]
    by_role = {o.role: o for o in ops}

    # Weighted vote; analysts with thin data get proportionally less say.
    num = sum(WEIGHTS[o.role] * o.score * (0.4 + 0.6 * o.coverage) for o in ops)
    den = sum(WEIGHTS[o.role] * (0.4 + 0.6 * o.coverage) for o in ops)
    composite = num / den if den else 0.0

    # ---- Round 2: debate
    all_pts = [p for o in ops for p in o.points if p.topic != "info"]
    bulls = sorted([p for p in all_pts if p.weight > 0], key=lambda p: -p.weight)
    bears = sorted([p for p in all_pts if p.weight < 0], key=lambda p: p.weight)
    debate: list[tuple[str, str]] = []
    if bulls:
        lead = " ".join(f"{p.text}" for p in bulls[:3])
        debate.append(("Ben (Bull)", f"Here is the case for owning {sd.name}. {lead}"))
    else:
        debate.append(("Ben (Bull)", f"Honestly, I struggle to find a positive argument for {sd.name} today."))
    if bears:
        lead = " ".join(f"{p.text}" for p in bears[:3])
        debate.append(("Bea (Bear)", f"I'm not convinced. {lead}"))
    else:
        debate.append(("Bea (Bear)", "I looked hard and found no serious red flags."))
    if bears:
        debate.append(("Ben (Bull), rebuttal", _bull_rebuttal(bears[0], bulls)))
    if bulls:
        debate.append(("Bea (Bear), rebuttal", _bear_rebuttal(bulls[0], bears)))

    # ---- Round 3: risk review
    rk = by_role["Risk Manager"]
    risk_notes: list[str] = []
    level = 2 + (2 if composite >= 0.35 else 1 if composite >= 0.15 else 0 if composite > -0.10 else -1 if composite > -0.30 else -2)
    max_weight = rk.extra["max_weight"]
    if rk.score <= -0.45 and level >= 3:
        level -= 1
        risk_notes.append("Risk profile is poor — I'm using my veto to downgrade the verdict one notch.")
    if max_weight < 0.05:
        if level >= 3:
            level = 2
        risk_notes.append(f"There is no room left in this sector under our {A.SECTOR_CAP * 100:.0f}% sector cap.")
    fund_cov = by_role["Fundamental Analyst"].coverage
    if fund_cov < 0.4 and level >= 3:
        level -= 1
        risk_notes.append("Fundamental data is too thin to commit with confidence — downgrading one notch.")
    vol = rk.extra.get("vol")
    risk_notes.append(
        f"Maximum position size: {max_weight * 100:.0f}% of the portfolio"
        + (f" (scaled for {vol * 100:.0f}% volatility)." if vol else ".")
    )
    risk_notes.append(f"Every order costs a €1 fee, like on Trade Republic. Stop-loss rule: review at {STOP_LOSS * 100:.0f}% from cost.")

    # ---- Round 4: chair
    verdict = LEVELS[level]
    chair: list[str] = []
    rsi = by_role["Technical Analyst"].extra.get("rsi")
    tech = by_role["Technical Analyst"].score
    if held:
        gain = sd.price_eur / held["avg_cost_eur"] - 1
        chair.append(f"We own {held['shares']:.4f} shares at an average cost of €{held['avg_cost_eur']:.2f}; position is {A.pct(gain)}.")
        if gain <= STOP_LOSS and tech < 0:
            verdict = "SELL"
            chair.append("Stop-loss triggered: down more than 15% and the trend is broken. Discipline says cut it.")
        elif gain >= TAKE_PROFIT and rsi and rsi > 75:
            verdict = "TRIM"
            chair.append("Up over 40% and overbought: let's bank half the profit and let the rest run.")
        elif verdict in ("BUY", "STRONG BUY"):
            verdict = "HOLD"
            chair.append("The thesis is intact. We keep holding.")
        elif verdict == "HOLD":
            chair.append("Nothing decisive either way. We hold and review again next time.")
        else:
            chair.append("The committee has turned negative on this holding.")

    scores = [o.score for o in ops]
    agree = sum(1 for s in scores if (s > 0) == (composite > 0)) / len(scores)
    strength = abs(composite)
    conviction = "High" if strength > 0.35 and agree >= 0.8 else "Medium" if strength > 0.15 and agree >= 0.6 else "Low"
    chair.insert(
        0,
        f"Weighted committee score is {composite:+.2f} on a scale of -1 to +1; "
        f"{int(agree * 5)} of 5 analysts lean the same way. Conviction: {conviction}.",
    )
    if not held:
        if verdict in ("BUY", "STRONG BUY"):
            chair.append(f"Decision: {verdict}. We propose a position of up to {max_weight * 100:.0f}% of the portfolio.")
        else:
            chair.append(f"Decision: {verdict} — we do not buy it today.")

    d = Decision(
        ticker=sd.ticker, name=sd.name, verdict=verdict, composite=composite, conviction=conviction,
        opinions=ops, debate=debate, risk_notes=risk_notes, chair_notes=chair, max_weight=max_weight,
        price_eur=sd.price_eur, sector=sd.sector, held=held,
    )
    d.transcript = render(sd, d)
    return d


def render(sd: A.StockData, d: Decision) -> str:
    i = sd.info
    today = dt.date.today().isoformat()
    lines = [
        f"# Investment committee — {sd.name} ({sd.ticker})",
        "",
        f"*{today}* · ISIN `{sd.isin}` · {sd.sector} / {i.get('industry', '?')}",
        "",
        f"**Price:** {sd.price:,.2f} {sd.currency} (≈ €{sd.price_eur:,.2f})"
        + (f" · **Market cap:** €{(i.get('marketCap') or 0) * sd.eur_rate / 1e9:,.1f}bn" if i.get("marketCap") else ""),
        "",
        f"> **Verdict: {d.verdict}** · score {d.composite:+.2f} · conviction {d.conviction}",
        "",
        "## Round 1 — Opening statements",
        "",
    ]
    for o in d.opinions:
        lines.append(f"### {o.persona}, {o.role} — {o.stance} ({o.score:+.2f})")
        if o.coverage < 0.5:
            lines.append(f"*Limited data: only {o.coverage * 100:.0f}% of this analyst's checks could be run.*")
        lines.append("")
        for p in o.points:
            mark = "🟢" if p.weight > 0 else "🔴" if p.weight < 0 else "⚪"
            lines.append(f"- {mark} {p.text}")
        lines.append("")
    lines += ["## Round 2 — Bull vs. Bear", ""]
    for who, said in d.debate:
        lines += [f"**{who}:** {said}", ""]
    lines += ["## Round 3 — Risk review", ""]
    for n in d.risk_notes:
        lines += [f"**Rita (Risk Manager):** {n}", ""]
    lines += ["## Round 4 — Chair's verdict", ""]
    for n in d.chair_notes:
        lines += [f"**Clara (Chair):** {n}", ""]
    return "\n".join(lines)
