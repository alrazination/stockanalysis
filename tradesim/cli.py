"""Command-line interface: python -m tradesim <command>."""

from __future__ import annotations

import argparse
import sys

from . import engine, market
from . import portfolio as P
from . import report as R
from .universe import UNIVERSE, lookup


def _ask(question: str, interactive: bool) -> bool:
    if not interactive:
        return False
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes", "j", "ja")
    except EOFError:
        return False


def _fmt_prop(p: dict) -> str:
    what = f"€{p['amount_eur']:.0f}" if p["action"] == "BUY" else f"{p['shares']:.4f} sh"
    return (
        f"{p['id']}  {p['action']:<4} {p['name']} ({p['ticker']})  {what} @ ~€{p['price_eur']:.2f}  "
        f"| {p['verdict']}, score {p['score']:+.2f}, conviction {p['conviction']}\n"
        f"      reasoning: {p['discussion']}"
    )


def _offer(pf: dict, props: list[dict], interactive: bool) -> None:
    if not props:
        print("\nThe committee has no trades to propose right now.")
        return
    print("\n=== The committee asks for your decision ===")
    saved = [P.add_proposal(pf, p) for p in props]
    for p in saved:
        print("\n" + _fmt_prop(p))
        if _ask(f"Execute {p['action']} {p['ticker']}?", interactive):
            tx = engine.execute(pf, p)
            print(f"   ✔ {tx['type']} {tx['shares']:.4f} {tx['ticker']} @ €{tx['price_eur']:.2f}. Cash left: €{pf['cash']:.2f}")
    left = [p for p in saved if p["status"] == "pending"]
    if left:
        ids = " ".join(p["id"] for p in left)
        print(f"\nPending proposals: {ids}\nApprove with:  python -m tradesim approve {ids}")


def _snapshot(pf: dict) -> tuple[dict, float | None]:
    prices = engine.holding_prices_eur(pf)
    bench = engine.bench_price()
    P.snapshot(pf, prices, bench)
    return prices, bench


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tradesim", description="Paper-trading simulator with an AI investment committee.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("deposit", help="add fake money (EUR)")
    d.add_argument("amount", type=float)
    s = sub.add_parser("scan", help="analyse the universe and propose buys")
    s.add_argument("--max-new", type=int, default=6)
    s.add_argument("--no-input", action="store_true", help="only save proposals, don't prompt")
    a = sub.add_parser("analyze", help="full committee discussion for one stock")
    a.add_argument("ticker")
    a.add_argument("--no-input", action="store_true")
    rv = sub.add_parser("review", help="re-evaluate holdings and propose sells")
    rv.add_argument("--no-input", action="store_true")
    sub.add_parser("proposals", help="list pending proposals")
    ap_ = sub.add_parser("approve", help="execute pending proposals")
    ap_.add_argument("ids", nargs="+")
    rj = sub.add_parser("reject", help="reject pending proposals")
    rj.add_argument("ids", nargs="+")
    b = sub.add_parser("buy", help="manual buy: TICKER EUR_AMOUNT")
    b.add_argument("ticker")
    b.add_argument("amount", type=float)
    se = sub.add_parser("sell", help="manual sell: TICKER [SHARES] (default: all)")
    se.add_argument("ticker")
    se.add_argument("shares", type=float, nargs="?")
    sub.add_parser("status", help="portfolio overview")
    rp = sub.add_parser("report", help="write the monthly report")
    rp.add_argument("--month", help="YYYY-MM (default: current month)")
    sub.add_parser("universe", help="list tradable stocks")
    sub.add_parser("export", help="write web/data.json for the Trading Arena page")
    args = ap.parse_args(argv)

    pf = P.load()
    interactive = sys.stdin.isatty() and not getattr(args, "no_input", False)

    if args.cmd == "deposit":
        P.deposit(pf, args.amount, engine.bench_price())
        print(f"Deposited €{args.amount:,.2f}. Cash: €{pf['cash']:,.2f}")

    elif args.cmd == "scan":
        decisions, props = engine.scan(pf, max_new=args.max_new)
        print("\nTop of the committee's ranking:")
        for dcs in decisions[:12]:
            print(f"  {dcs.composite:+.2f}  {dcs.verdict:<11} {dcs.name} ({dcs.ticker}) — {dcs.sector}")
        _offer(pf, props, interactive)

    elif args.cmd == "analyze":
        dcs = engine.analyze(pf, args.ticker)
        if not dcs:
            print(f"No usable data for {args.ticker}.")
            return 1
        print(dcs.transcript)
        print(f"(saved to {dcs.extra['file']})")
        props = []
        if dcs.wants_buy:
            total = P.value(pf, engine.holding_prices_eur(pf))
            amount = float(int(min(dcs.max_weight * total, pf["cash"] - P.FEE_EUR) // 5 * 5))
            if amount >= P.MIN_ORDER_EUR:
                props.append({"action": "BUY", "ticker": dcs.ticker, "name": dcs.name, "isin": lookup(dcs.ticker)["isin"],
                              "sector": dcs.sector, "amount_eur": amount, "price_eur": round(dcs.price_eur, 4),
                              "verdict": dcs.verdict, "score": round(dcs.composite, 3), "conviction": dcs.conviction,
                              "discussion": dcs.extra["file"]})
        elif dcs.wants_sell:
            sh = pf["positions"][dcs.ticker]["shares"] * (0.5 if dcs.verdict == "TRIM" else 1)
            props.append({"action": "SELL", "ticker": dcs.ticker, "name": dcs.name, "shares": round(sh, 6),
                          "price_eur": round(dcs.price_eur, 4), "verdict": dcs.verdict, "score": round(dcs.composite, 3),
                          "conviction": dcs.conviction, "discussion": dcs.extra["file"]})
        _offer(pf, props, interactive)

    elif args.cmd == "review":
        decisions, props = engine.review(pf)
        for dcs in decisions:
            print(f"  {dcs.composite:+.2f}  {dcs.verdict:<11} {dcs.name} ({dcs.ticker})  → {dcs.extra['file']}")
        _offer(pf, props, interactive)

    elif args.cmd == "proposals":
        pend = P.pending(pf)
        print("\n\n".join(_fmt_prop(p) for p in pend) if pend else "No pending proposals.")

    elif args.cmd in ("approve", "reject"):
        pend = {p["id"]: p for p in P.pending(pf)}
        for pid in args.ids:
            p = pend.get(pid.upper())
            if not p:
                print(f"{pid}: not a pending proposal (maybe expired — re-run scan).")
                continue
            if args.cmd == "reject":
                p["status"] = "rejected"
                print(f"{pid}: rejected.")
                continue
            try:
                tx = engine.execute(pf, p)
                print(f"{pid}: {tx['type']} {tx['shares']:.4f} {tx['ticker']} @ €{tx['price_eur']:.2f} (fee €1). Cash: €{pf['cash']:.2f}")
            except Exception as exc:
                print(f"{pid}: failed — {exc}")

    elif args.cmd == "buy":
        t = args.ticker.upper()
        info = market.get_info(t)
        px = market.last_prices([t])[t] * market.eur_per(info.get("currency"))
        meta = {**lookup(t), "sector": info.get("sector", "Unknown")}
        tx = P.buy(pf, t, meta, args.amount, px)
        print(f"Bought {tx['shares']:.4f} {t} @ €{px:.2f}. Cash: €{pf['cash']:.2f}")

    elif args.cmd == "sell":
        t = args.ticker.upper()
        px = market.last_prices([t])[t] * market.eur_per(market.get_info(t).get("currency"))
        tx = P.sell(pf, t, args.shares, px)
        print(f"Sold {tx['shares']:.4f} {t} @ €{px:.2f}, realised €{tx['realized_pnl']:+.2f}. Cash: €{pf['cash']:.2f}")

    elif args.cmd == "status":
        prices, bench = _snapshot(pf)
        print("\n".join(R.status_lines(pf, prices, bench)))
        print()
        print("\n".join(R.positions_table(pf, prices)))
        pend = P.pending(pf)
        if pend:
            print(f"\n{len(pend)} pending proposal(s): python -m tradesim proposals")

    elif args.cmd == "report":
        prices, bench = _snapshot(pf)
        path = R.monthly(pf, prices, bench, args.month)
        print(path.read_text())
        print(f"(saved to {path.relative_to(R.ROOT)})")

    elif args.cmd == "export":
        from .export import export

        print(f"Wrote {export().relative_to(R.ROOT)}")
        return 0

    elif args.cmd == "universe":
        for t, n, isin, region in UNIVERSE:
            print(f"{t:<10} {isin}  {region}  {n}")

    if args.cmd not in ("universe", "proposals"):
        if args.cmd not in ("status", "report"):
            _snapshot(pf)
        P.save(pf)
    elif args.cmd == "proposals":
        P.save(pf)
    return 0
