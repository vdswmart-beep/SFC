"""Model parameters, read by model.py. The web app (app.py) can override LONG_ONLY with its toggle.
Data-source settings (tickers, dates) live in fetch_yahoo.py and bloomberg_to_csv.py."""

# --- The switch ---
LONG_ONLY = False  # True: the SHORT leg is skipped; the LONGs are held fully invested, no hedge

# --- Universe size: values for the EURO STOXX 50; for the STOXX Europe 600 use 5 and 50 ---
MIN_SECTOR_SIZE = 3  # scored stocks a sector needs before pairs are formed in it
MIN_STOCKS_DATE = 20  # scored stocks needed to invest at a date

# --- Signals ---
SIGNALS = ["value", "momentum", "quality", "lowvol"]  # each also gets a single-factor strategy
MIN_SIGNALS = 3  # signals a stock needs to get a composite score
FUND_LAG = 3  # months between a fiscal period end and the publication of its accounts

# --- Portfolio ---
N_POSITIONS = 12  # total positions, half LONG and half SHORT (even number): 20 -> 10 + 10
EXCL_THRESHOLD = -1.0  # H1: no LONG with any z below -1, no SHORT with any z above +1
BETA_HEDGE = True  # long/short only: sell index futures for the pocket's beta (beta-neutral)
BETA_WINDOW = 36  # months of the pocket's own past returns used to estimate its beta
SMART_BETA_TOP = 0.20  # long-only reference: best 20% of scored stocks, equally weighted

# --- Costs ---
TC_BPS = 10  # transaction cost, bps per unit of turnover
BORROW_BPS_YR = 50  # borrow fee on shorted stocks, bps per year
TC_GRID_BPS = [0, 10, 20]  # H3 sensitivity: transaction costs tested
BORROW_GRID_BPS_YR = [0, 50, 100]  # H3 sensitivity: borrow fees tested

# --- Evaluation ---
MAIN_STRATEGY = "Composite + exclusion"  # used for the positions, the charts and the cost grid
HOLDOUT_START = "2021-01-01"  # final test sample: never look at it while developing the model
SHOW_HOLDOUT = True  # True in the Yahoo phase; False with Bloomberg until the final test
SIGNIFICANCE = 0.05  # one-sided level of the Sharpe test against the benchmark
NW_LAGS = 6  # Newey-West lags for the t-stat of the alpha
STRESS_PERIODS = {  # first and last month of each stress test
    "GFC 2008-09": ("2008-09", "2009-03"),
    "Euro crisis 2011-12": ("2011-07", "2012-06"),
    "Covid 2020": ("2020-02", "2020-04"),
    "Inflation 2022": ("2022-01", "2022-12"),
}
OUTPUT_DIR = "output"  # tables (CSV), report.xlsx and charts (PNG) are written here
