"""Tests of the web app's explanations: sector exposure, reasons, ranking, holdings, moves."""
import numpy as np
import pandas as pd
import pytest

from src import explain
from src.data import make_fake_data
from src.portfolio import ls_weights
from src.signals import composite, compute_signals, sector_zscore


@pytest.fixture(scope="module")
def run() -> dict:
    """Fake data, their z-scores, the composite score and the long/short weights."""
    data = make_fake_data(n_stocks=300)
    raw = compute_signals(data["tr"], data["btp"], data["roe"], fund_lag=3)
    z = {k: sector_zscore(v, data["member"], data["sectors"]) for k, v in raw.items()}
    score = composite(z, 3)
    weights = ls_weights(score, data["sectors"], n_long=8, n_short=4, max_sector_share=0.25,
                         min_sector_size=3, min_stocks_date=20)
    return {"z": z, "score": score, "weights": weights, "sectors": data["sectors"]}


def test_sector_exposure(run: dict) -> None:
    """LONGs add up to +100 % and SHORTs to -50 % over the sectors; net = LONG + SHORT; no
    sector holds more than 2 of the 8 LONGs."""
    exposure = explain.sector_exposure(run["weights"].iloc[-1], run["sectors"])
    assert np.isclose(exposure["LONG"].sum(), 1.0) and np.isclose(exposure["SHORT"].sum(), -0.5)
    assert np.allclose(exposure["Net"], exposure["LONG"] + exposure["SHORT"])
    assert exposure["LONG"].max() <= 2 / 8 + 1e-9


def test_why() -> None:
    """The signals for the side first, strongest first, then the strong ones against it."""
    z = pd.Series({"value": 2.0, "momentum": -1.5, "quality": 0.2, "lowvol": 0.6})
    assert explain.why(z, "LONG") == "cheap (+2.0), steady (+0.6); but falling (-1.5)"
    assert explain.why(z, "SHORT") == "falling (-1.5); but cheap (+2.0)"
    assert explain.why(z * 0, "LONG") == "no single strong signal"


def test_ranking_at(run: dict) -> None:
    """Every scored stock once, best first, and exactly the 8 LONGs and 4 SHORTs marked."""
    date = run["score"].index[-1]
    table = explain.ranking_at(date, run["score"], run["z"], run["sectors"], run["weights"])
    assert len(table) == run["score"].loc[date].notna().sum()
    assert table["Score"].is_monotonic_decreasing
    assert (table["Side"] == "LONG").sum() == 8 and (table["Side"] == "SHORT").sum() == 4


def test_holdings_and_moves(run: dict) -> None:
    """The heatmap cells are the non-zero weights; moves compare two consecutive months."""
    weights, end = run["weights"], run["weights"].index[-1]
    cells = explain.holdings(weights, run["sectors"], end, months=12)
    assert len(cells) == (weights.tail(12) != 0).sum().sum()
    entered, left = explain.moves(weights, end)
    now, before = weights.iloc[-1] != 0, weights.iloc[-2] != 0
    assert sorted(entered) == sorted(now.index[now & ~before])
    assert sorted(left) == sorted(now.index[before & ~now])
