"""Portfolio page: the lines held at a month-end and why, the full ranking, the holdings."""
import altair as alt
import pandas as pd
import streamlit as st

import config
from app_pages.common import current_run, show, styled
from model import SMART_BETA, ranking_score
from src import explain
from src.report import positions_table

RED, GRAY, BLUE = "#c8453c", "#d9d8d2", "#2a78d6"  # SHORT, small weight, LONG
ROW_COLORS = {"LONG": "#e6effb", "SHORT": "#f9e7e5"}


def lines_and_why(run: dict, name: str, date: pd.Timestamp) -> None:
    """The positions held at `date` with their reasons in words, then the pairs behind them."""
    score = ranking_score(name, run["z"], run["score"])
    lines = positions_table(run["strategies"][name], score, run["z"], run["sectors"], date)
    show(styled(explain.with_reasons(lines.drop(columns="Date"))))
    st.caption("Score: the stock's composite score (its signal's z-score for a single-factor "
               "strategy). z: how far the stock is from its sector's average, in standard "
               "deviations. Why: the signals with |z| ≥ 0.5 for its side, then those against it.")
    if name != SMART_BETA:  # the smart beta holds the best scores, without pairs
        st.subheader("The pairs behind the lines")
        pairs = explain.pairs_at(run["long_short"][name].loc[date], score.loc[date],
                                 run["sectors"])
        show(styled(pairs))
        st.caption("Spread: LONG score − SHORT score. Weight: spread / sum of the spreads."
                   + (" Long-only: the SHORTs are skipped, the LONGs keep their weight."
                      if run["long_only"] else ""))
    with st.expander("Raw values behind the z-scores"):
        raw = pd.DataFrame({k: v.loc[date, lines.index] for k, v in run["raw"].items()})
        show(raw.style.format("{:.3f}"))
        st.caption(f"value = B/P and quality = ROE, both {config.FUND_LAG} months old; "
                   "momentum = 12-1 month return; lowvol = minus the monthly volatility.")


def _highlight(row: pd.Series) -> list[str]:
    """Background of a ranking row: blue for a LONG, red for a SHORT, none otherwise."""
    color = ROW_COLORS.get(row["Side"])
    return [f"background-color: {color}" if color else ""] * len(row)


def full_ranking(run: dict, name: str, date: pd.Timestamp) -> None:
    """Every scored stock at `date`, best score first, the stocks held highlighted."""
    score = ranking_score(name, run["z"], run["score"])
    table = explain.ranking_at(date, score, run["z"], run["sectors"], run["strategies"][name])
    sector = st.selectbox("Sector", ["All sectors"] + sorted(table["Sector"].unique()))
    if sector != "All sectors":
        table = table[table["Sector"] == sector]
    show(styled(table).apply(_highlight, axis=1), height=600)
    st.caption(f"{len(table)} stocks. Pairs are formed inside a sector with at least "
               f"{config.MIN_SECTOR_SIZE} scored stocks: the LONG near its top (Rank in "
               "sector), the SHORT near its bottom; only the "
               f"{config.N_POSITIONS // 2} widest spreads are kept.")


def _heatmap(cells: pd.DataFrame) -> alt.Chart:
    """One row per stock, sorted by sector, one column per month; blue = LONG, red = SHORT."""
    cells = cells.assign(Stock=cells["Sector"] + " · " + cells["Ticker"])
    limit = cells["Weight"].abs().max()
    # "lab": a straight fade from gray to each color (the default bends through other hues)
    color = alt.Scale(domain=[-limit, 0, limit], range=[RED, GRAY, BLUE], interpolate="lab")
    return alt.Chart(cells).mark_rect().encode(
        x=alt.X("Month:O", title=None),
        y=alt.Y("Stock:N", sort="ascending", title=None,
                axis=alt.Axis(labelOverlap=False, labelLimit=320)),
        color=alt.Color("Weight:Q", scale=color, legend=alt.Legend(format="%", title="Weight")),
        tooltip=["Month", "Ticker", "Sector", "Side", alt.Tooltip("Weight:Q", format=".1%")],
    ).properties(height=20 * cells["Stock"].nunique() + 40)


def holdings_over_time(run: dict, name: str, date: pd.Timestamp) -> None:
    """The weights of the months up to `date` as a heatmap, then what changed at `date`."""
    weights = run["strategies"][name]
    months = st.slider("Months shown, up to the chosen month-end", 6, 120, 36, step=6)
    st.altair_chart(_heatmap(explain.holdings(weights, run["sectors"], date, months)))
    entered, left = explain.moves(weights, date)
    turnover = weights.diff().abs().sum(axis=1).loc[date]
    st.markdown(f"**At {date:%Y-%m}**: in {', '.join(entered) or 'none'} · out "
                f"{', '.join(left) or 'none'} · turnover {turnover:.0%} (sum of weight changes)")


run = current_run()
st.title("Portfolio")
st.caption(run["mode"])
names = list(run["strategies"])
default = names.index(config.MAIN_STRATEGY) if config.MAIN_STRATEGY in names else 0
name = st.selectbox("Strategy", names, index=default)
weights = run["strategies"][name]
dates = weights.index[weights.abs().sum(axis=1) > 0].tolist()  # month-ends with positions
if not dates:
    st.warning(f"{name} holds no position with these data.")
    st.stop()
date = st.select_slider("Month-end", dates, value=dates[-1], format_func=lambda d: f"{d:%Y-%m}")
st.caption(f"Decided at the close of {date:%d %B %Y} with the data known then, held during "
           "the following month.")
tab_lines, tab_ranking, tab_holdings = st.tabs(["Lines held and why", "Full ranking",
                                                "Holdings over time"])
with tab_lines:
    lines_and_why(run, name, date)
with tab_ranking:
    full_ranking(run, name, date)
with tab_holdings:
    holdings_over_time(run, name, date)
