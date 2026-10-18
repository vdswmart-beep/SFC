# ls_backtest: equitized long/short multi-factor backtest (V1)

## 1. Purpose
Monthly backtest of an **equitized** strategy: full benchmark exposure (index futures) plus a
self-financing long/short pocket, beta-neutral and sector-neutral, built on four signals (value,
momentum, quality, low volatility). This is the V1 of the master's thesis *From Smart Beta to
Active Management*: the simplest correct model, on which hypotheses H1 to H4 are tested.
Phase 1 uses the EURO STOXX 50 with free Yahoo Finance data; phase 2 the STOXX Europe 600 with
Bloomberg. Only the data source changes between the two.

One switch, `LONG_ONLY` in `config.py` (or the toggle of the web app), skips the SHORT leg: the
same LONGs are then held alone, fully invested, and compared with the index. A web app explains
the model, maps the code and shows the stocks held and why (section 7).

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
streamlit run app.py        # the web app, in your browser (section 7)
python -m pytest            # tests
```
Bloomberg: section 4.3. Every run of `main.py` prints the tables and writes to
`output/long_short/` (or `output/long_only/` when `LONG_ONLY = True`, so the two reports sit
side by side): one CSV per table, `report.xlsx` (one formatted sheet per table),
`cumulative.png` and `drawdown.png`. The fake data have no factor premium: IRs close to zero or
negative are expected there.

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
- **Prices**: Yahoo's adjusted prices can turn negative far back in time (AB InBev before 2009);
  `load_data` treats a non-positive level as missing.

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
5. `python main.py data/bloomberg`, or choose `data/bloomberg` in the web app.

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
├── .streamlit/config.toml   look and settings of the web app
├── config.py                every model parameter, including the LONG_ONLY switch
├── model.py                 the model in one call: data -> signals -> pairs -> switch -> tables
├── main.py                  command line: runs model.py, prints and writes the outputs
├── app.py                   web app: sidebar (data, switch) and navigation between the pages
├── fetch_yahoo.py           Yahoo connector -> data/yahoo/*.csv
├── bloomberg_to_csv.py      Bloomberg connector: refreshed workbook -> data/bloomberg/*.csv
├── bloomberg/
│   └── SXXP_extraction.xlsx Bloomberg formulas (empty template, see its README sheet)
├── src/                     the model: pure functions, parameters passed as arguments
│   ├── __init__.py          empty: makes src a package
│   ├── data.py              reads the CSV files, generates fake data
│   ├── signals.py           raw signals, sector z-scores, composite score
│   ├── portfolio.py         LONG/SHORT pairs; the switch (skip_short_leg); smart beta reference
│   ├── backtest.py          net returns of the pocket (beta-hedged) and of the total portfolio
│   ├── metrics.py           annualized statistics, Sharpe test, Fama-French alpha
│   ├── regimes.py           market regimes (trend x volatility)
│   ├── report.py            result tables
│   ├── charts.py            growth of 1 and drawdown charts
│   ├── export.py            writes CSV files, report.xlsx and PNG charts (the only side effects)
│   └── explain.py           the "why" of the web app: pairs, reasons, ranking, entries and exits
├── app_pages/               one file per page of the web app
│   ├── __init__.py          empty: makes app_pages a package
│   ├── common.py            the current run and the look of the tables
│   ├── how_it_works.py      the model as a recipe, with the file and function of each step
│   ├── code_map.py          where to change what, the role of each file, the code itself
│   ├── portfolio.py         the lines held and why, the full ranking, the holdings over time
│   └── performance.py       key figures, charts and the tables of the Excel report
├── tests/
│   ├── test_sanity.py       neutrality, positions, universe, look-ahead, hedge, switch
│   ├── test_explain.py      pairs rebuilt from the weights, reasons, ranking, moves
│   └── test_app.py          every page of the web app runs, in both modes
├── data/
│   ├── yahoo/               CSV files from Yahoo (not versioned)
│   └── bloomberg/           refreshed workbook and its CSV files (not versioned)
└── output/                  results of main.py: long_short/ and long_only/
```
`main.py` and `app.py` both call `run_model` (`model.py`), so the command line and the web app
always show the same numbers. `src/` never reads `config.py`: `model.py` passes the parameters
to its functions as arguments.

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
6. **The switch** (`LONG_ONLY`, `skip_short_leg`): `False` (default) keeps the long/short
   pocket on top of the index. `True` skips the SHORT leg of every pair strategy: the same LONGs,
   which already total 100 %, are held alone, fully invested, without futures or borrow fees; the
   active return is then the portfolio's return minus the index's. The web app's toggle does the
   same without editing `config.py`.
7. **Beta hedge** (long/short only): the pocket's beta is estimated on its own past 36 monthly
   returns (12 at least, `BETA_WINDOW`), and index futures are sold for that beta during the next
   month. The betas of single stocks would be biased: they are estimated on the same months that
   selected the stocks, and they over-hedge the pocket (on fake data, the low-vol pocket hedged
   with stock betas ended with a beta of +0.7 instead of 0; hedged with its own past beta,
   about 0).
8. **Smart beta reference** (long-only in both modes): the best 20 % of scored stocks
   (`SMART_BETA_TOP`), equally weighted, never hedged: what a multi-factor smart beta ETF would
   hold.
9. **Backtest**: pocket = sum of weights x returns - costs - hedge, where costs = turnover x 10 bps
   (`TC_BPS`) + |SHORTs| x 50 bps / 12 (`BORROW_BPS_YR`). Total portfolio = benchmark return +
   pocket. For a long-only portfolio, the pocket is its return minus the benchmark's, so the
   total is simply the portfolio's return. All strategies start on the same month (the latest
   start among them).

The strategies compared: the four single-factor pocket strategies (`Single value`, ...),
`Composite`, `Composite + exclusion` (the main strategy) and `Smart beta (long-only)`.

## 7. The web app
```bash
cd ~/SFC/ls_backtest
streamlit run app.py        # opens http://localhost:8501 in the browser; Ctrl+C to stop
```
The sidebar picks the **data** (every folder of `data/` that holds the CSV files, or the fake
data) and the **mode** (the long-only toggle, by default `LONG_ONLY`). Four pages:
- **How it works**: the recipe of section 6 as a diagram and seven steps, each with its file and
  function, filled with the current values of `config.py`.
- **Code map**: where to change what, the role of every file and function (read from the
  docstrings, so always up to date), and the code of any file with line numbers.
- **Portfolio**: for a strategy and a month-end, the lines held with their z-scores and the
  reasons in words; the pairs behind them (LONG, SHORT, spread, weight); the full ranking of the
  scored stocks with the held ones highlighted; a heatmap of the holdings over time with the
  stocks that entered and left.
- **Performance**: the key figures of the main strategy, growth of 1 and drawdown, and the tables
  of the Excel report.

The model runs once per data source and mode (a few seconds on Yahoo data, about 20 on the
fake data, which have 800 stocks like the STOXX Europe 600), then the app reads it from memory.
A change to the code, to `config.py` or to the data files re-runs it automatically. The app runs
on your machine only: nothing is sent anywhere.

## 8. Evaluation: what each output shows
| Table / chart | Content | Hypothesis |
|---|---|---|
| Summary | active return, tracking error, IR (for a long/short pocket, which is self-financing, also its Sharpe ratio), t-stat, max drawdown of the active return, active beta, turnover, Sharpe of the total portfolio and of the benchmark; full sample, before the hold-out, hold-out | H1 |
| Sharpe test | Jobson-Korkie test with Memmel's correction: total portfolio Sharpe above the benchmark's? one-sided p-value | definition of a persistent Sharpe |
| Alpha | Fama-French 5 factors + momentum, Newey-West t-stat (needs `factors.csv`) | H1 |
| Regimes | IR in each regime: Bull/Bear (12-month benchmark return) x high/low vol (12-month vol against its past median), known one month ahead | H4 |
| Stress tests | cumulative return of the benchmark and active return of each strategy: GFC 2008-09, euro crisis 2011-12, Covid 2020, inflation 2022 | H3, H4 |
| Costs | IR of the main strategy for transaction costs 0/10/20 bps x borrow fees 0/50/100 bps a year | H3 |
| Positions | the current lines of the main strategy (12, or 6 in long-only mode): side, weight, sector, score, z-scores | applying the strategy |
| Monthly returns | active return of every strategy, every month | further analysis |
| cumulative.png, drawdown.png | main strategy vs smart beta vs benchmark, total portfolios | thesis figures |

The thesis calls a Sharpe ratio persistent when it is (1) measured out of sample and net of
costs: the hold-out and the cost grid; (2) statistically above the benchmark's: the Sharpe test;
(3) superior in every regime: the regime table. The pocket target is an IR above 1.5.

**Hold-out discipline**: 2021-2025 (`HOLDOUT_START`) is the final test sample. With Bloomberg
data, keep `SHOW_HOLDOUT = False` while developing: every table and chart then stops in December
2020. Switch it on once, for the final test.

## 9. Time convention
Weights are set at the end of month t with the information available at t, then applied to the
return from t to t+1 (`weights.shift(1)` in `backtest.py`); the costs and the hedge decided at t
are charged to month t+1. `test_no_lookahead` checks the mechanics: a signal that knows next
month's return must give an IR above 10, a signal built on past returns an |IR| below 2.

## 10. Known simplifications
- The hedge uses the pocket's realized beta: it lags when the portfolio changes, the first 12
  months are not hedged, and futures costs and basis are ignored.
- 12 lines: high tracking error, results driven by few stocks (`N_POSITIONS` raises it).
- A missing return counts as 0 (no delisting return); turnover ignores the drift of weights
  between rebalancings; the borrow fee is the same for every stock.
- Current GICS sectors applied to the whole history (Communication Services was created in 2018).
- The Sharpe test assumes independent, normal returns; Ledoit and Wolf (2008) is the robust
  alternative.

## 11. How to extend
- **More positions**: `N_POSITIONS` in `config.py` (even number: 20 = 10 LONG + 10 SHORT).
- **A signal**: 1 line in `compute_signals` + 1 name in `SIGNALS`; it automatically gets a
  single-factor strategy and enters the composite (give it words in `WORDS`, `src/explain.py`,
  for the web app).
- **A strategy**: 1 line in `build_strategies` (`model.py`).
- **A metric**: 1 key in `perf_stats`; it appears in every summary.
- **A table**: 1 function in `report.py` + 1 line in `build_tables` (`model.py`); it gets its own
  CSV file, Excel sheet and tab in the web app.
- **A page of the web app**: 1 file in `app_pages/` + 1 line in `app.py`.
- **Another source**: a script that writes the six CSV files of section 4.1.

## 12. Roadmap
1. Bloomberg extraction of the STOXX Europe 600 (workbook ready) and French factors in EUR.
2. Piotroski F-score inside the score or as a filter (H2).
3. Short-sale bans, margin calls and borrow fees per stock (H3).
4. Euro-area recession regimes (H4).
5. Constrained optimization of the pocket (Jacobs, Levy and Markowitz, 2005).
6. Walk-forward as soon as a parameter is estimated on the data; Ledoit-Wolf Sharpe test.
