"""Web app: the sidebar picks the data and the mode (the long-only switch); four pages explain
the model and show what it holds and how it did. Start it with `streamlit run app.py` here."""
from pathlib import Path

import streamlit as st

import config
from model import run_model
from src.data import load_data, make_fake_data

HERE = Path(__file__).parent
FAKE = "Fake data (demo)"


def data_sources() -> list[str]:
    """Every folder of data/ that holds the model's CSV files, then the fake data."""
    found = HERE.glob("data/*/tr_index.csv")
    return sorted(path.parent.relative_to(HERE).as_posix() for path in found) + [FAKE]


def last_change(source: str) -> float:
    """Time of the latest change to the code, config.py or the data files of `source`."""
    files = [*HERE.glob("*.py"), *HERE.glob("src/*.py"), *(HERE / source).glob("*.csv")]
    return max(path.stat().st_mtime for path in files)


@st.cache_data(max_entries=4, show_spinner="Running the model...")  # e.g. 2 sources x 2 modes
def cached_run(source: str, long_only: bool, changed: float) -> dict:
    """run_model, computed once per data source and mode, then served from memory. `changed`
    (see last_change) is only there so that editing the code, config.py or the data re-runs it."""
    data = make_fake_data() if source == FAKE else load_data(str(HERE / source))
    return run_model(data, long_only)


st.set_page_config(page_title="ls_backtest", page_icon=":material/query_stats:", layout="wide")
source = st.sidebar.selectbox("Data", data_sources())
long_only = st.sidebar.toggle(
    "Long-only: skip the SHORT leg", value=config.LONG_ONLY,
    help="On: the same LONGs, no SHORT, fully invested, no hedge. Off: index + LONG/SHORT "
         "pocket. The default is LONG_ONLY in config.py.")
try:
    st.session_state["run"] = cached_run(source, long_only, last_change(source))
except SystemExit as stop:  # the model stops with a message when the data cannot be used
    st.error(str(stop))
    st.stop()
st.sidebar.caption(st.session_state["run"]["mode"])
st.navigation([
    st.Page("app_pages/how_it_works.py", title="How it works", icon=":material/menu_book:",
            default=True),
    st.Page("app_pages/code_map.py", title="Code map", icon=":material/account_tree:"),
    st.Page("app_pages/portfolio.py", title="Portfolio", icon=":material/pie_chart:"),
    st.Page("app_pages/performance.py", title="Performance", icon=":material/monitoring:"),
]).run()
