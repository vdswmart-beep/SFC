"""Performance page: the key figures, the charts, the stress periods and the tables of the Excel
report."""
import pandas as pd
import streamlit as st

import config
from app_pages.charts import line_chart
from app_pages.common import current_run, show, styled
from src.charts import growth_and_drawdown
from src.export import PERCENT_SHEETS

NOTES = {  # what each table answers (README section 8)
    "Summary": "Annualized. Active = return above the index; IR = active return / tracking "
               "error; Active beta = sensitivity of the active return to the index.",
    "Sharpe test": "Is the portfolio's Sharpe ratio above the index's? Jobson-Korkie test with "
                   "Memmel's correction, one-sided.",
    "Alpha": "Alpha of the active return against the Fama-French factors; Newey-West t-stat.",
    "Regimes": "IR in each market regime: bull or bear (12-month index return) x high or low "
               "volatility, known a month ahead (H4).",
    "Stress tests": "Cumulative return of the index, then active return of each strategy, over "
                    "each crisis (H3, H4).",
    "Costs": "IR of the main strategy for each pair of cost assumptions (H3).",
    "Monthly returns": "Active return of every strategy, every month.",
}


def key_figures(tables: dict) -> None:
    """The headline numbers of the main strategy over the full sample."""
    main = config.MAIN_STRATEGY
    if main not in tables["Sharpe test"].index:
        return  # the main strategy has no position with these data
    stats, test = tables["Summary"].loc[("Full sample", main)], tables["Sharpe test"].loc[main]
    st.subheader(main)
    columns = st.columns(5)
    columns[0].metric("Active return (ann.)", f"{stats['Active return (ann.)']:.1%}")
    columns[1].metric("Information ratio", f"{stats['IR']:.2f}")
    sharpe, index_sharpe = test["Sharpe (total)"], test["Sharpe (benchmark)"]
    columns[2].metric("Sharpe ratio", f"{sharpe:.2f}", f"{sharpe - index_sharpe:+.2f} vs index")
    columns[3].metric("Max drawdown (active)", f"{stats['Max DD (active)']:.1%}")
    columns[4].metric("Sharpe test p-value", f"{test['p-value']:.2f}",
                      help=f"Below {config.SIGNIFICANCE}: Sharpe ratio significantly above the "
                           "index's.")


def stress_charts(curves: pd.DataFrame) -> None:
    """Growth of 1 of the total portfolios over each stress period that lies in the sample."""
    inside = {label: (start, end) for label, (start, end) in config.STRESS_PERIODS.items()
              if not curves.loc[start:end].empty}
    if not inside:
        st.info(f"No stress period lies in the sample ({curves.index[0]:%Y-%m} to "
                f"{curves.index[-1]:%Y-%m}). Yahoo's accounts start in 2022: for 20 years of "
                "price signals, set SIGNALS = ['momentum', 'lowvol'] and MIN_SIGNALS = 2 in "
                "config.py, or use the Bloomberg data.")
        return
    label = st.radio("Stress period", list(inside), horizontal=True)
    start, end = inside[label]
    growth, _ = growth_and_drawdown(curves.loc[start:end])
    st.altair_chart(line_chart(growth, ".2f"))
    st.caption("Growth of 1 of the total portfolios (long/short: index + pocket), from the month "
               "before the stress period. The table above shows the returns above the index.")


def result_tables(run: dict) -> None:
    """The tables of the Excel report, one tab each (Positions: see the Portfolio page), with
    the charts of the stress periods under their table."""
    tables = run["tables"]
    titles = [title for title in tables if title != "Positions"]
    for tab, title in zip(st.tabs(titles), titles, strict=True):
        with tab:
            st.caption(NOTES.get(title, ""))
            table = tables[title]
            if title == "Summary":
                period = st.radio("Period", table.index.unique("Period"), horizontal=True)
                table = table.loc[period]
            height = 600 if title == "Monthly returns" else "content"  # 1 row per month
            show(styled(table, all_percent=title in PERCENT_SHEETS), height)
            if title == "Stress tests":
                stress_charts(run["curves"])


run = current_run()
months = run["curves"].index
st.title("Performance")
st.caption(f"{run['mode']} · {months[0]:%Y-%m} to {months[-1]:%Y-%m} ({len(months)} months) · "
           "net of costs")
key_figures(run["tables"])
growth, drawdown = growth_and_drawdown(run["curves"])
left, right = st.columns(2)
with left:
    st.markdown("**Growth of 1, net of costs**")
    st.altair_chart(line_chart(growth, ".2f"))
with right:
    st.markdown("**Drawdown from the previous peak**")
    st.altair_chart(line_chart(drawdown, ".0%"))
result_tables(run)
