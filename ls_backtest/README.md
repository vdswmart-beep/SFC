# ls_backtest: equitized long/short multi-factor backtest (V1)

## 1. Purpose
Monthly backtest of an **equitized** strategy: full benchmark exposure (index futures) plus a
self-financing long/short pocket, beta-neutral and sector-neutral, built on four signals (value,
momentum, quality, low volatility). This is the V1 of the master's thesis *From Smart Beta to
Active Management*: the simplest correct model, on which hypotheses H1 to H4 are tested.
Phase 1 uses the EURO STOXX 50 with free Yahoo Finance data; phase 2 the STOXX Europe 600 with
Bloomberg. Only the data source changes between the two.

## 2. Installation
Python 3.11 or later.
```bash
cd ~/SFC/ls_backtest
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Running
```bash
python main.py              # fake data, no connection needed
python fetch_yahoo.py       # downloads the EURO STOXX 50 into data/yahoo/ (a few minutes)
python main.py data/yahoo   # backtest on those files
python -m pytest            # sanity tests
```
Bloomberg: section 4.3. Every run prints the tables and writes to `output/`: one CSV per table,
`report.xlsx` (one formatted sheet per table), `cumulative.png` and `drawdown.png`.
The fake data have no factor premium: IRs close to zero or negative are expected there.

## 4. Data
### 4.1 Six CSV files: the only contact with the source
The model only reads these files. Format: first column = month-end date `YYYY-MM-DD` (the last
business day is accepted), then one column per ticker, with the same tickers in every file.

| File | Content | Yahoo (`fetch_yahoo.py`) | Bloomberg (`bloomberg_to_csv.py`) |
|---|---|---|---|
| `tr_index.csv` | total return index per stock | dividend-adjusted price (`Adj Close`) | `TOT_RETURN_INDEX_GROSS_DVDS`, in EUR |
| `book_to_price.csv` | B/P = book equity / market value | (`Common Stock Equity` / shares) / price | 1 / `PX_TO_BOOK_RATIO` |
| `roe.csv` | return on equity, decimal | net income / common equity | `RETURN_COM_EQY` / 100 |
| `member.csv` | 1 if in the index at that month-end, else 0 | 1 as soon as the stock trades | `INDX_MWEIGHT_HIST` on `SXXP Index` |
| `sector.csv` | columns `ticker, sector` (GICS) | `UNIVERSE` in `fetch_yahoo.py` | `GICS_SECTOR_NAME` |
| `bench.csv` | columns `date, bench, rf`: index level, 1-month rate (annual %) | `^STOXX50E`, rf = 0 | `SXXGR Index`, `EUR001M Index` |
| `factors.csv` (optional) | `date, Mkt-RF, SMB, HML, RMW, CMA, WML`, in % | not produced | Kenneth French library, in EUR |

### 4.2 Yahoo Finance (phase 1: EURO STOXX 50)
`fetch_yahoo.py` writes `data/yahoo/`. Its limits, all lifted by Bloomberg:
- **Accounts**: Yahoo keeps 4 fiscal years only, so value, quality and the composite start around
  2023 and every strategy is aligned on that date. For a 20-year test of the price signals alone:
  `SIGNALS = ["momentum", "lowvol"]` and `MIN_SIGNALS = 2` in `config.py`.
- **Universe**: current composition only (survivorship bias: past members are missing).
- **Benchmark and rf**: price index (no dividends) and rf = 0 %: the total return and the Sharpe
  ratios are approximate; the pocket (IR, alpha) is not affected.
- **Currency**: B/P dropped for companies reporting in USD (Prosus, argenx).

### 4.3 Bloomberg (phase 2: STOXX Europe 600)
The workbook `bloomberg/SXXP_extraction.xlsx` holds the Bloomberg formulas; its README sheet
gives every step. In short:
1. On a Bloomberg terminal (Excel add-in, Microsoft 365), save a copy of the workbook. The
   members load by themselves (step 1); then switch the downloads ON one at a time in `Params`
   (universe, TR, PB, ROE: Bloomberg caps the data per user and per day), and save.
2. Put the refreshed copy in `data/bloomberg/` (ignored by git: the data are licensed).
3. `python bloomberg_to_csv.py data/bloomberg/SXXP_extraction.xlsx` writes the CSV files next
   to it and prints the checks (months loaded, stocks without prices, stocks without sector).
4. In `config.py`: `MIN_SECTOR_SIZE = 5`, `MIN_STOCKS_DATE = 50`, `SHOW_HOLDOUT = False`.
5. `python main.py data/bloomberg`.

The universe is every stock that was in the index at any month-end from 2005 to 2025, delisted
stocks included; prices start in 2002 so that momentum and volatility exist from 2005.
The benchmark is `SXXGR Index` (gross return), like-for-like with the stocks' gross total
returns; `SXXR Index` is the net return version. Fama-French factors come from Kenneth French's
data library (Europe 5 factors + momentum), in USD: market in EUR =
(1 + Mkt-RF + RF) x (1 + change of the USD against the EUR) - 1, minus the EUR rf; the
long/short factors (SMB to WML) are only affected at the second order. Without `factors.csv`,
the alpha table is skipped.

## 5. Project tree
```
ls_backtest/
├── README.md
├── requirements.txt         dependencies
├── .gitignore               data/ and output/ are never versioned
├── config.py                every model parameter (only main.py reads it)
├── main.py                  orchestration: data -> signals -> weights -> backtests -> outputs
├── fetch_yahoo.py           Yahoo connector -> data/yahoo/*.csv
├── bloomberg_to_csv.py      Bloomberg connector: refreshed workbook -> data/bloomberg/*.csv
├── bloomberg/
│   └── SXXP_extraction.xlsx Bloomberg formulas (empty template, see its README sheet)
├── src/
│   ├── __init__.py          empty: makes src a package
│   ├── data.py              reads the CSV files, generates fake data
│   ├── signals.py           raw signals, sector z-scores, composite score
│   ├── portfolio.py         LONG/SHORT pairs; long-only smart beta reference
│   ├── backtest.py          net returns of the pocket (beta-hedged) and of the total portfolio
│   ├── metrics.py           annualized statistics, Sharpe test, Fama-French alpha
│   ├── regimes.py           market regimes (trend x volatility)
│   ├── report.py            result tables
│   ├── charts.py            growth of 1 and drawdown charts
│   └── export.py            writes CSV files, report.xlsx and PNG charts (the only side effects)
├── tests/
│   └── test_sanity.py       neutrality, positions, universe, look-ahead, hedge, references
├── data/
│   ├── yahoo/               CSV files from Yahoo (not versioned)
│   └── bloomberg/           refreshed workbook and its CSV files (not versioned)
└── output/                  results, created by each run
```

## 6. The model, step by step
1. **Monthly returns**: r(t) = TR(t) / TR(t-1) - 1, dividends included.
2. **Raw signals** (higher = more attractive): value = B/P 3 months ago and quality = ROE 3 months
   ago (`FUND_LAG`: accounts are published with a delay); momentum = TR(t-1) / TR(t-12) - 1
   (12-1: the last month, dominated by short-term reversal, is skipped); low vol = minus the
   standard deviation of the last 36 monthly returns (24 at least).
3. **Sector z-scores**: for each signal, month and GICS sector, z = (value - sector mean) /
   sector standard deviation, on index members only, capped at +/-3. A bank is compared with
   banks, and ratios, percentages and volatilities become comparable.
4. **Composite score**: equal-weighted mean of the available z-scores (25 % each), only for stocks
   with at least 3 of the 4 signals (`MIN_SIGNALS`).
5. **LONG/SHORT pairs** (`ls_weights`), every month-end:
   - the month is invested only with at least `MIN_STOCKS_DATE` scored stocks;
   - in every sector with at least `MIN_SECTOR_SIZE` scored stocks, stocks are ranked by score
     and paired: best (LONG) against worst (SHORT), then 2nd best against 2nd worst, and so on,
     while the LONG still scores above the SHORT;
   - the `N_POSITIONS / 2` pairs with the widest score spread, all sectors together, are kept
     (6 pairs for 12 positions);
   - each pair weighs its spread / sum of the kept spreads: the LONG gets +w, the SHORT -w. LONGs
     total +100 %, SHORTs -100 %, and every sector nets to 0 because a pair never leaves its
     sector;
   - exclusion variant (H1): no LONG with any factor z below -1 (`EXCL_THRESHOLD`), no SHORT
     with any factor z above +1.
6. **Beta hedge**: the pocket's beta is estimated on its own past 36 monthly returns (12 at
   least, `BETA_WINDOW`), and index futures are sold for that beta during the next month. The
   betas of single stocks would be biased: they are estimated on the same months that selected
   the stocks, and they over-hedge the pocket (on fake data, the low-vol pocket hedged with stock
   betas ended with a beta of +0.7 instead of 0; hedged with its own past beta, about 0).
7. **Smart beta reference** (long-only): the best 20 % of scored stocks (`SMART_BETA_TOP`),
   equally weighted, never hedged: what a multi-factor smart beta ETF would hold.
8. **Backtest**: pocket = sum of weights x returns - costs - hedge, where costs = turnover x 10 bps
   (`TC_BPS`) + |SHORTs| x 50 bps / 12 (`BORROW_BPS_YR`). Total portfolio = benchmark return +
   pocket. For the long-only reference, the pocket is its return minus the benchmark's. All
   strategies start on the same month (the latest start among them).

The strategies compared: the four single-factor pocket strategies (`Single value`, ...),
`Composite`, `Composite + exclusion` (the main strategy) and `Smart beta (long-only)`.

## 7. Evaluation: what each output shows
| Table / chart | Content | Hypothesis |
|---|---|---|
| Summary | active return, tracking error, IR (= pocket Sharpe: the pocket is self-financing), t-stat, max drawdown, residual beta, turnover, Sharpe of the total portfolio and of the benchmark; full sample, before the hold-out, hold-out | H1 |
| Sharpe test | Jobson-Korkie test with Memmel's correction: total portfolio Sharpe above the benchmark's? one-sided p-value | definition of a persistent Sharpe |
| Alpha | Fama-French 5 factors + momentum, Newey-West t-stat (needs `factors.csv`) | H1 |
| Regimes | pocket IR in each regime: Bull/Bear (12-month benchmark return) x high/low vol (12-month vol against its past median), known one month ahead | H4 |
| Stress tests | cumulative return of the benchmark and of each pocket: GFC 2008-09, euro crisis 2011-12, Covid 2020, inflation 2022 | H3, H4 |
| Costs | pocket IR of the main strategy for transaction costs 0/10/20 bps x borrow fees 0/50/100 bps a year | H3 |
| Positions | the 12 current lines of the main strategy: side, weight, sector, score, z-scores | applying the strategy |
| Monthly returns | pocket return of every strategy, every month | further analysis |
| cumulative.png, drawdown.png | main strategy vs smart beta vs benchmark, total portfolios | thesis figures |

The thesis calls a Sharpe ratio persistent when it is (1) measured out of sample and net of
costs: the hold-out and the cost grid; (2) statistically above the benchmark's: the Sharpe test;
(3) superior in every regime: the regime table. The pocket target is an IR above 1.5.

**Hold-out discipline**: 2021-2025 (`HOLDOUT_START`) is the final test sample. With Bloomberg
data, keep `SHOW_HOLDOUT = False` while developing: every table and chart then stops in December
2020. Switch it on once, for the final test.

## 8. Time convention
Weights are set at the end of month t with the information available at t, then applied to the
return from t to t+1 (`weights.shift(1)` in `backtest.py`); the costs and the hedge decided at t
are charged to month t+1. `test_no_lookahead` checks the mechanics: a signal that knows next
month's return must give an IR above 10, a signal built on past returns an |IR| below 2.

## 9. Known simplifications
- The hedge uses the pocket's realized beta: it lags when the portfolio changes, the first 12
  months are not hedged, and futures costs and basis are ignored.
- 12 lines: high tracking error, results driven by few stocks (`N_POSITIONS` raises it).
- A missing return counts as 0 (no delisting return); turnover ignores the drift of weights
  between rebalancings; the borrow fee is the same for every stock.
- Current GICS sectors applied to the whole history (Communication Services was created in 2018).
- The Sharpe test assumes independent, normal returns; Ledoit and Wolf (2008) is the robust
  alternative.

## 10. How to extend
- **More positions**: `N_POSITIONS` in `config.py` (even number: 20 = 10 LONG + 10 SHORT).
- **A signal**: 1 line in `compute_signals` + 1 name in `SIGNALS`; it automatically gets a
  single-factor strategy and enters the composite.
- **A strategy**: 1 line in `build_strategies` (`main.py`).
- **A metric**: 1 key in `perf_stats`; it appears in every summary.
- **A table**: 1 function in `report.py` + 1 line in `build_tables`; it gets its own CSV file and
  Excel sheet.
- **Another source**: a script that writes the six CSV files of section 4.1.

## 11. Roadmap
1. Bloomberg extraction of the STOXX Europe 600 (workbook ready) and French factors in EUR.
2. Piotroski F-score inside the score or as a filter (H2).
3. Short-sale bans, margin calls and borrow fees per stock (H3).
4. Euro-area recession regimes (H4).
5. Constrained optimization of the pocket (Jacobs, Levy and Markowitz, 2005).
6. Walk-forward as soon as a parameter is estimated on the data; Ledoit-Wolf Sharpe test.
