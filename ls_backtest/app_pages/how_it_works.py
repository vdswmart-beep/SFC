"""How it works page: the model as a recipe, step by step, with the file and function of each."""
import streamlit as st

import config
from app_pages.common import current_run

HALF = config.N_POSITIONS // 2  # LONGs, and SHORTs
PIPELINE = """digraph {
  rankdir=LR; bgcolor="transparent"; nodesep=0.25;
  node [shape=box, style="rounded,filled", fillcolor="#eaf2fc", color="#2a78d6",
        fontname="Helvetica", fontsize=13];
  edge [color="#8c8b85"];
  data [label="1 Data\\nsrc/data.py"]; signals [label="2 Signals\\nsrc/signals.py"];
  scores [label="3 Scores\\nsrc/signals.py"]; select [label="4 LONG / SHORT\\nsrc/portfolio.py"];
  switch [label="5 Switch\\nLONG_ONLY", shape=diamond, fillcolor="#fdeee8", color="#eb6834"];
  backtest [label="6 Backtest\\nsrc/backtest.py"]; results [label="7 Results\\nsrc/report.py"];
  data -> signals -> scores -> select -> switch -> backtest -> results;
}"""
STEPS = [  # (title, where in the code, what happens)
    ("Data", "src/data.py → load_data", """
One CSV file per variable, one row per month-end, one column per stock: total return index
(dividends included), book-to-price, ROE, index membership (1/0), GICS sector, benchmark and
risk-free rate, and the optional Fama-French factors. They are written by `fetch_yahoo.py`
(EURO STOXX 50) or `bloomberg_to_csv.py` (STOXX Europe 600). Without a folder, the model runs on
fake data that hold no factor premium."""),
    ("Signals", "src/signals.py → compute_signals", f"""
Four raw signals per stock, oriented so that higher = more attractive:
- **Value**: book-to-price (B/P = book equity / market value), {config.FUND_LAG} months ago,
  because accounts are published with a delay;
- **Momentum**: the return from 12 months ago to 1 month ago (the last month is skipped: it
  tends to reverse);
- **Quality**: return on equity (ROE), {config.FUND_LAG} months ago;
- **Low volatility**: minus the volatility of the last 36 monthly returns."""),
    ("Scores", "src/signals.py → sector_zscore, composite", f"""
Each signal becomes a **z-score inside its sector**, at each month-end, among index members:
z = (value − sector mean) / sector standard deviation, capped at ±3. A bank is compared with
banks only. The **composite score** is the average of a stock's z-scores (each signal weighs
the same), if it has at least {config.MIN_SIGNALS} of the {len(config.SIGNALS)}."""),
    ("LONG / SHORT", "src/portfolio.py → ls_weights", f"""
All scored stocks are ranked by score: the **{HALF} best go LONG, the {HALF} worst go SHORT**,
with at most {config.MAX_PER_SECTOR} stocks of one sector on each side, so that the book spreads
over the sectors. A LONG must score above its sector's average, a SHORT below; sectors with fewer
than {config.MIN_SECTOR_SIZE} scored stocks are left out. Equal weights: each LONG weighs
+100 % / {HALF}, each SHORT −100 % / {HALF}. Variant `Composite + exclusion` (H1, the main
strategy): no LONG with a z-score below {config.EXCL_THRESHOLD:+.0f} on any signal, no SHORT with
one above {-config.EXCL_THRESHOLD:+.0f}. A month with fewer than {config.MIN_STOCKS_DATE} scored
stocks is not invested."""),
    ("The switch", "config.py → LONG_ONLY (or the sidebar toggle); src/portfolio.py → "
     "skip_short_leg", f"""
- **Long/short** (toggle off): the portfolio holds the index plus the LONG/SHORT pocket. Index
  futures are sold for the pocket's beta, estimated on its own last {config.BETA_WINDOW} monthly
  returns, so the pocket does not depend on the market's direction.
- **Long-only** (toggle on): the SHORT leg is skipped. The same LONGs, which already total
  100 %, are the whole portfolio: fully invested, no futures, no borrow fee.

The **smart beta reference** is long-only in both modes: the best {config.SMART_BETA_TOP:.0%} of
scored stocks by composite score, equally weighted."""),
    ("Backtest", "src/backtest.py → run_backtest", f"""
Weights set at the end of month t earn the return from t to t+1: the model never uses
information it would not have had. Costs: {config.TC_BPS} bps per unit of turnover, plus
{config.BORROW_BPS_YR} bps a year on the SHORTs. **Active return** = portfolio − index."""),
    ("Results", "src/metrics.py, src/regimes.py, src/report.py", f"""
Information ratio (active return / tracking error), Sharpe test against the index
(Jobson-Korkie-Memmel), alpha against the Fama-French factors, market regimes (H4), stress
tests, cost grid (H3), and the hold-out sample from {config.HOLDOUT_START[:4]}: see the
**Performance** page. `python main.py` writes the same tables to an Excel report."""),
]

st.title("How it works")
st.markdown("Every month-end the model follows the same recipe. Each step names the file and "
            "the function that do it: the **Code map** page shows the code.")
st.graphviz_chart(PIPELINE, width="stretch")
for number, (title, where, text) in enumerate(STEPS, start=1):
    with st.container(border=True):
        st.markdown(f"#### {number}. {title}")
        st.caption(where)
        st.markdown(text)
st.info(f"Mode shown now: **{current_run()['mode']}**. Switch it in the sidebar.")
