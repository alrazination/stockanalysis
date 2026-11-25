"""Portfolio status and the end-of-month performance report."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import portfolio as P

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def _eur(x: float) -> str:
    return f"€{x:,.2f}"


def _pct(x: float) -> str:
    return f"{x * 100:+.2f}%"


def positions_table(pf: dict, prices: dict[str, float]) -> list[str]:
    total = P.value(pf, prices) or 1
    rows = [
        "| Stock | Shares | Avg cost | Price | Value | P&L | Weight |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for t, p in sorted(pf["positions"].items(), key=lambda kv: -kv[1]["shares"] * prices.get(kv[0], 0)):
        px = prices.get(t, p["avg_cost_eur"])
        val = p["shares"] * px
        pnl = val - p["shares"] * p["avg_cost_eur"]
        rows.append(
            f"| {p['name']} ({t}) | {p['shares']:.4f} | {_eur(p['avg_cost_eur'])} | {_eur(px)} | {_eur(val)} "
            f"| {_eur(pnl)} ({_pct(px / p['avg_cost_eur'] - 1)}) | {val / total * 100:.1f}% |"
        )
    rows.append(f"| Cash | | | | {_eur(pf['cash'])} | | {pf['cash'] / total * 100:.1f}% |")
    return rows


def status_lines(pf: dict, prices: dict[str, float], bench_now: float | None) -> list[str]:
    val, inv = P.value(pf, prices), P.invested(pf)
    lines = [
        f"Portfolio value: {_eur(val)}   (deposited {_eur(inv)})",
        f"Total return:    {_eur(val - inv)} ({_pct(val / inv - 1) if inv else 'n/a'})",
    ]
    bv = P.bench_value(pf, bench_now)
    if bv:
        lines.append(f"MSCI World ETF:  {_eur(bv)} ({_pct(bv / inv - 1)}) had the same deposits gone there")
    return lines


def monthly(pf: dict, prices: dict[str, float], bench_now: float | None, month: str | None = None) -> Path:
    month = month or dt.date.today().strftime("%Y-%m")
    start = dt.date.fromisoformat(month + "-01")
    snaps = sorted(pf["snapshots"], key=lambda s: s["date"])
    before = [s for s in snaps if s["date"] < start.isoformat()]
    start_val = before[-1]["value"] if before else 0.0
    start_bench = before[-1].get("bench_value") if before else 0.0

    in_month = lambda d: d[:7] == month  # noqa: E731
    deps = sum(d["amount"] for d in pf["deposits"] if in_month(d["date"]))
    txs = [t for t in pf["transactions"] if in_month(t["date"]) and t["type"] != "DEPOSIT"]
    realized = sum(t.get("realized_pnl", 0) for t in txs)
    fees = sum(t.get("fee", 0) for t in txs)

    val, inv = P.value(pf, prices), P.invested(pf)
    month_pnl = val - start_val - deps
    base = start_val + deps
    bv = P.bench_value(pf, bench_now)
    bench_month = (bv - (start_bench or 0) - deps) if bv is not None and start_bench is not None else None

    L = [
        f"# Monthly report — {start.strftime('%B %Y')}",
        "",
        f"*Generated {P.now()} · paper money, Trade Republic rules (€1/order, fractional shares, no taxes)*",
        "",
        "## Headline",
        "",
        "| | Amount |",
        "|---|---:|",
        f"| Value at start of month | {_eur(start_val)} |",
        f"| Deposits this month | {_eur(deps)} |",
        f"| Value now | {_eur(val)} |",
        f"| **Profit/loss this month** | **{_eur(month_pnl)} ({_pct(month_pnl / base) if base else 'n/a'})** |",
        f"| Total deposited | {_eur(inv)} |",
        f"| **Total profit/loss since start** | **{_eur(val - inv)} ({_pct(val / inv - 1) if inv else 'n/a'})** |",
        f"| Realised P&L this month | {_eur(realized)} |",
        f"| Fees this month | {_eur(fees)} |",
    ]
    if bv is not None:
        L.append(f"| Benchmark (MSCI World ETF, same deposits) | {_eur(bv)} ({_pct(bv / inv - 1)}) |")
        if bench_month is not None:
            L.append(f"| Benchmark profit/loss this month | {_eur(bench_month)} |")
        diff = val - bv
        L += ["", f"**{'Beating' if diff >= 0 else 'Trailing'} the benchmark by {_eur(abs(diff))}.**"]
    L += ["", "## Positions", ""] + positions_table(pf, prices)
    L += ["", "## Trades this month", ""]
    if txs:
        L += ["| Date | Action | Stock | Shares | Price | Amount | Realised |", "|---|---|---|---:|---:|---:|---:|"]
        for t in txs:
            L.append(
                f"| {t['date'][:10]} | {t['type']} | {t['ticker']} | {t['shares']:.4f} | {_eur(t['price_eur'])} "
                f"| {_eur(t['amount_eur'])} | {_eur(t['realized_pnl']) if 'realized_pnl' in t else ''} |"
            )
    else:
        L.append("No trades.")
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{month}.md"
    path.write_text("\n".join(L) + "\n")
    return path
