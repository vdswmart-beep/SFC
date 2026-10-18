"""Helpers shared by the pages of the web app: the current run and the look of the tables."""
import pandas as pd
import streamlit as st
from pandas.io.formats.style import Styler

from src.export import PERCENT_COLUMNS

WHOLE_NUMBERS = {"Months", "Rank", "Rank in sector"}


def current_run() -> dict:
    """The model run for the data and the mode chosen in the sidebar (computed by app.py)."""
    return st.session_state["run"]


def styled(table: pd.DataFrame, all_percent: bool = False) -> Styler:
    """A table formatted like the Excel report: returns and weights in %, ratios with 2
    decimals, counts and ranks as whole numbers."""
    formats = {}
    for column in table.select_dtypes("number").columns:
        if all_percent or column in PERCENT_COLUMNS:
            formats[column] = "{:.1%}"
        else:
            formats[column] = "{:.0f}" if column in WHOLE_NUMBERS else "{:.2f}"
    return table.style.format(formats)


def show(table: pd.DataFrame | Styler, height: int | str = "content") -> None:
    """Displays a table: by default every row visible, without an inner scroll bar; missing
    values left blank instead of 'None'."""
    st.dataframe(table, height=height, placeholder="")
