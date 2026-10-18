"""Sanity tests on fake data: neutrality, positions, universe, look-ahead, hedge, switch."""
import numpy as np
import pandas as pd
import pytest

from src.backtest import run_backtest
from src.data import make_fake_data
from src.metrics import perf_stats, sharpe_test
from src.portfolio import long_only_weights, ls_weights, skip_short_leg
from src.signals import composite, compute_signals, sector_zscore

PARAMS = dict(n_positions=12, min_sector_size=3, min_stocks_date=20)


@pytest.fixture(scope="module")
def data() -> dict:
    """Fake data set shared by every test."""
    return make_fake_data(n_stocks=300)


@pytest.fixture(scope="module")
def zscores(data: dict) -> dict[str, pd.DataFrame]:
    """Sector z-scores of the four signals."""
    raw = compute_signals(data["tr"], data["btp"], data["roe"], fund_lag=3)
    return {k: sector_zscore(v, data["member"], data["sectors"]) for k, v in raw.items()}


@pytest.fixture(scope="module", params=[False, True], ids=["composite", "exclusion"])
def weights(request: pytest.FixtureRequest, data: dict, zscores: dict) -> pd.DataFrame:
    """Weights of the composite strategy, without then with the exclusion variant."""
    excl = dict(zscores=zscores, excl_threshold=-1.0) if request.param else {}
    return ls_weights(composite(zscores, 3), data["sectors"], **PARAMS, **excl)


def _stats(z: pd.DataFrame, data: dict, beta_window: int | None = None) -> pd.Series:
    """Statistics of a single-signal strategy without costs: isolates the mechanics."""
    w = ls_weights(z, data["sectors"], **PARAMS)
    returns = data["tr"].pct_change(fill_method=None)
    res = run_backtest(w, returns, data["bench_ret"], data["rf"], 0, 0, beta_window)
    return perf_stats(res, data["bench_ret"], data["rf"])


def test_weights_neutral(weights: pd.DataFrame, data: dict) -> None:
    """LONGs = +1, SHORTs = -1 and every sector nets to 0."""
    w = weights.iloc[-1]
    assert np.isclose(w[w > 0].sum(), 1.0)
    assert np.isclose(w[w < 0].sum(), -1.0)
    assert np.allclose(w.groupby(data["sectors"]).sum(), 0.0)


def test_position_count(weights: pd.DataFrame) -> None:
    """Exactly n_positions stocks held, half LONG, half SHORT."""
    w = weights.iloc[-1]
    assert (w > 0).sum() == (w < 0).sum() == PARAMS["n_positions"] // 2


def test_no_non_members(weights: pd.DataFrame, data: dict) -> None:
    """No weight on a stock outside the index at that date."""
    assert not weights.where(data["member"] == 0).fillna(0.0).to_numpy().any()


def test_no_lookahead(data: dict) -> None:
    """A signal that knows the future must explode; a signal on the past must not."""
    ret = data["tr"].pct_change(fill_method=None)
    cheat = sector_zscore(ret.shift(-1), data["member"], data["sectors"])  # knows t -> t+1
    past = sector_zscore(ret, data["member"], data["sectors"])  # past returns only
    assert _stats(cheat, data)["IR"] > 10
    assert abs(_stats(past, data)["IR"]) < 2


def test_beta_hedge(zscores: dict, data: dict) -> None:
    """Low vol buys low-beta stocks: unhedged, the pocket's beta is clearly negative;
    hedged with index futures, it is close to 0."""
    assert _stats(zscores["lowvol"], data)["Active beta"] < -0.2
    assert abs(_stats(zscores["lowvol"], data, beta_window=36)["Active beta"]) < 0.1


def test_long_only(weights: pd.DataFrame) -> None:
    """The switch: the SHORT leg is skipped; the same LONGs stay, fully invested."""
    w, long_only = weights.iloc[-1], skip_short_leg(weights).iloc[-1]
    assert (long_only >= 0).all() and np.isclose(long_only.sum(), 1.0)
    assert long_only[long_only > 0].equals(w[w > 0])


def test_smart_beta(zscores: dict) -> None:
    """Long-only reference: the best 20 % of scored stocks, equally weighted, fully invested."""
    score = composite(zscores, 3)
    w = long_only_weights(score, top=0.2, min_stocks_date=20).iloc[-1]
    assert np.isclose(w.sum(), 1.0) and (w < 0).sum() == 0
    assert (w > 0).sum() == round(0.2 * score.iloc[-1].notna().sum())


def test_sharpe_test(data: dict) -> None:
    """A constant extra return beats the benchmark's Sharpe; a constant loss does not."""
    bench = data["bench_ret"]
    assert sharpe_test(bench + 0.002, bench, data["rf"])["p-value"] < 0.05
    assert sharpe_test(bench - 0.002, bench, data["rf"])["p-value"] > 0.95
