"""Portfolio page: the lines held at a month-end and why, the full ranking, the sector exposure and
the holdings over time."""
import pandas as pd
import streamlit as st

import config
from app_pages.charts import heatmap, sector_bars
from app_pages.common import current_run, show, styled
from model import ranking_score
from src import explain
from src.report import positions_table

ROW_COLORS = {"LONG": "#e6effb", "SHORT": "#f9e7e5"}


def lines_and_why(run: dict, name: str, date: pd.Timestamp) -> None:
    """The positions held at `date` with their reasons in words, and the raw data behind them."""
    score = ranking_score(name, run["z"], run["score"])
    lines = positions_table(run["strategies"][name], score, run["z"], run["sectors"], date)
    show(styled(explain.with_reasons(lines.drop(columns="Date"))))
    st.caption("Score: the stock's composite score (its signal's z-score for a single-factor "
               "strategy). z: how far the stock is from its sector's average, in standard "
               "deviations. Why: the signals with |z| ≥ 0.5 for its side, then those against it.")
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
    st.caption(f"{len(table)} stocks. LONG: the {config.N_LONG} best scores, SHORT: the "
               f"{config.N_SHORT} worst; one sector holds at most {config.MAX_SECTOR_SHARE:.0%} "
               "of each side (Rank in sector shows who that limit kept out), and only sectors "
               f"with {config.MIN_SECTOR_SIZE}+ scored stocks count.")


def sector_exposure(run: dict, name: str, date: pd.Timestamp) -> None:
    """LONG, SHORT and net weight of each sector at `date`, then the net weights over time."""
    weights = run["strategies"][name]
    exposure = explain.sector_exposure(weights.loc[date], run["sectors"])
    st.altair_chart(sector_bars(exposure))
    st.caption("Weight of each sector among the LONGs (+100 % in total) and the SHORTs; the "
               "black tick is the net, LONG + SHORT. The pocket's net long weight is offset by "
               "selling index futures.")
    months = st.slider("Months shown, up to the chosen month-end", 6, 120, 36, step=6,
                       key="sector_months")
    cells = explain.holdings(weights, run["sectors"], date, months)
    net = cells.groupby(["Month", "Sector"], as_index=False)["Weight"].sum()
    st.markdown("**Net exposure by sector over time**")
    st.altair_chart(heatmap(net, "Sector"))


def holdings_over_time(run: dict, name: str, date: pd.Timestamp) -> None:
    """The weights of the months up to `date` as a heatmap, then what changed at `date`."""
    weights = run["strategies"][name]
    months = st.slider("Months shown, up to the chosen month-end", 6, 120, 36, step=6)
    cells = explain.holdings(weights, run["sectors"], date, months)
    st.altair_chart(heatmap(cells.assign(Stock=cells["Sector"] + " · " + cells["Ticker"]),
                            "Stock"))
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
tab_lines, tab_ranking, tab_sectors, tab_holdings = st.tabs(
    ["Lines held and why", "Full ranking", "Sector exposure", "Holdings over time"])
with tab_lines:
    lines_and_why(run, name, date)
with tab_ranking:
    full_ranking(run, name, date)
with tab_sectors:
    sector_exposure(run, name, date)
with tab_holdings:
    holdings_over_time(run, name, date)
