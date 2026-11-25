# Trade Republic paper-trading simulator

A paper-money trading simulator for ~90 large stocks you can buy on **Trade Republic**.
For each stock, a virtual **investment committee** holds a four-round discussion,
reaches a verdict and then **asks you** whether to buy or sell. All trades use fake money,
and a monthly report shows how the portfolio is doing against simply buying the MSCI World.

## How a decision is made

Each stock goes through four rounds. The full transcript is saved under `discussions/<date>/<TICKER>.md`.

| Round | Who | What they look at |
|---|---|---|
| 1. Opening statements | **Fiona** (Fundamentals) | revenue and earnings growth, margins, ROE, debt, free cash flow |
| | **Victor** (Valuation) | forward P/E (adjusted for growth), PEG, EV/EBITDA, FCF yield, P/S, P/B for banks |
| | **Tara** (Technicals) | 50/200-day averages, RSI, MACD, distance from 52-week high |
| | **Sam** (Sentiment & Momentum) | analyst ratings and price targets, 6-month return vs. MSCI World, short interest, latest headlines |
| | **Rita** (Risk) | volatility, drawdown, beta, size, sector concentration in *your* portfolio |
| 2. Bull vs. Bear | **Ben** & **Bea** | the strongest three arguments on each side, then a rebuttal from each |
| 3. Risk review | **Rita** | position size (scaled to volatility, ≤ 25% per stock, ≤ 30% per sector), veto if the risk profile is poor |
| 4. Verdict | **Clara** (Chair) | weighted vote (Fund. 30%, Val. 25%, Tech. 20%, Sent. 15%, Risk 10%) → STRONG BUY … STRONG SELL, plus a conviction level |

For stocks you already hold, the committee also applies a **stop-loss**: it sells if the position is down 15% and the trend is broken. It also **takes profit**: it sells half if the position is up 40% and overbought.

Trading rules match Trade Republic: an EUR account, a **€1 fee per order**, fractional shares, and a €100 minimum order. Each round of buys keeps 5% in cash and adds at most one new stock per sector. Taxes are not simulated.

## Setup

```bash
pip install -r requirements.txt
```

Market data comes from Yahoo Finance via `yfinance`, so no API key is needed. Prices in USD, CHF or DKK are converted to EUR.

## Usage

```bash
python -m tradesim deposit 2000        # add fake money
python -m tradesim scan                # analyse all stocks, propose buys, ask you y/n for each
python -m tradesim analyze ASML.AS     # full committee discussion on one stock
python -m tradesim review              # re-check holdings, propose sells
python -m tradesim proposals           # list pending proposals
python -m tradesim approve P001 P003   # execute proposals (at the live price)
python -m tradesim reject P002
python -m tradesim buy SAP.DE 250      # manual override: buy €250
python -m tradesim sell SAP.DE         # manual override: sell all (or give a share count)
python -m tradesim status              # value, P&L, positions, vs. benchmark
python -m tradesim report              # write reports/YYYY-MM.md (run on the last day of the month)
python -m tradesim universe            # list the stocks the committee can choose from
```

`scan`, `analyze` and `review` ask for confirmation in a terminal. Add `--no-input` to only save proposals (they expire after 5 days).

## Files

| Path | Contents |
|---|---|
| `data/portfolio.json` | cash, positions, every transaction, proposals, daily value snapshots |
| `discussions/` | committee transcripts, one per stock per day |
| `reports/` | monthly performance reports |
| `tradesim/universe.py` | the stock list (ticker, name, ISIN); add or remove names here |

## Trading Arena (the game view)

`web/index.html` is a game-style page built from `web/data.json`. Write that file with
`python -m tradesim export`. The page has:

- a **race track**: the committee's portfolio against the MSCI World, placed by % return
- **decision cards** for every proposal, with each analyst's score and **Approve / Pass** buttons
- the **committee room**, which replays each debate as a chat between Fiona, Victor, Tara, Sam, Rita, Ben, Bea and Clara
- your positions with sparklines, the scouting board (today's ranking), **XP and levels**, a trophy cabinet and the trade log

It is published as a private claude.ai artifact. Your Approve and Pass taps are saved in the artifact's
database, and only you can make them. On the next run, Claude reads them and runs
`python -m tradesim approve|reject <ids>` at live prices. It then runs `export` and republishes the page.

## Monthly routine

1. Run `review` and decide on any sells.
2. Run `scan` to put free cash to work.
3. At month end, run `report`.

The report shows profit or loss for the month and since the start. It also compares the portfolio against the same deposits put into the iShares Core MSCI World ETF (EUNL).

> This is a simulation for learning. The committee is a rules-based model fed with public data; it is not financial advice.
