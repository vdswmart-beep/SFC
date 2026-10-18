"""Performance page: the key figures, the charts and the tables of the Excel report."""
import altair as alt
import pandas as pd
import streamlit as st

import config
from app_pages.common import current_run, show, styled
from src.charts import COLORS, growth_and_drawdown
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


def line_chart(lines: pd.DataFrame, number_format: str) -> alt.Chart:
    """One line per column, in the colors of the report's charts, with values on hover."""
    long = lines.rename_axis("Month").reset_index().melt("Month", var_name="Series",
                                                          value_name="Value")
    colors = alt.Scale(domain=list(lines.columns), range=COLORS[: len(lines.columns)])
    return alt.Chart(long).mark_line().encode(
        x=alt.X("Month:T", title=None, axis=alt.Axis(format="%Y", tickCount="year")),
        y=alt.Y("Value:Q", title=None, axis=alt.Axis(format=number_format),
                scale=alt.Scale(zero=False)),
        color=alt.Color("Series:N", scale=colors, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("Month:T", format="%Y-%m"), "Series",
                 alt.Tooltip("Value:Q", format=number_format)],
    )


def result_tables(tables: dict) -> None:
    """The tables of the Excel report, one tab each (Positions: see the Portfolio page)."""
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
result_tables(run["tables"])
