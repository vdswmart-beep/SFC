"""Monthly backtest of an equitized strategy: benchmark exposure + self-financing pocket."""
import pandas as pd

# Time convention: weights are set at the end of month t with the information available at t,
# then applied to the return from t to t+1. Hence weights.shift(1) against the returns, and the
# costs and the futures hedge decided at t charged to month t+1.


def _hedge(active: pd.Series, bench: pd.Series, rf: pd.Series, window: int) -> pd.Series:
    """Pocket made beta-neutral by selling index futures for its beta. The beta comes from the
    pocket's own past returns (`window` months, at least a third of it), known at t."""
    # betas of single stocks, estimated on the months that selected them, are biased and
    # over-hedge the pocket (README section 8); the pocket's realized beta is not
    rolling = dict(window=window, min_periods=window // 3)
    beta = active.rolling(**rolling).cov(bench) / bench.rolling(**rolling).var()
    return active - beta.shift(1).fillna(0.0) * (bench - rf)  # short futures earn -(index - rf)


def run_backtest(weights: pd.DataFrame, returns: pd.DataFrame, bench_ret: pd.Series,
                 rf: pd.Series, tc_bps: float, borrow_bps_yr: float,
                 beta_window: int | None = None) -> pd.DataFrame:
    """Monthly net returns of the active pocket and of the total portfolio.
    beta_window: None = no hedge, else the pocket's beta is sold with index futures.
    Inputs: wide (dates x tickers) and monthly Series; output: [active, total, turnover]."""
    returns = returns.reindex_like(weights).fillna(0.0)  # missing return = 0: see README
    gross = (weights.shift(1) * returns).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).shift(1)
    short_gross = weights.clip(upper=0).abs().sum(axis=1).shift(1)
    costs = turnover * tc_bps / 1e4 + short_gross * borrow_bps_yr / 1e4 / 12
    # a long-only portfolio already holds the market: only its return above the benchmark is
    # active (net exposure 1); a LONG/SHORT pocket has net exposure 0 and is active as a whole
    active = gross - costs - weights.sum(axis=1).shift(1) * bench_ret
    first = weights.index[weights.abs().sum(axis=1) > 0][0]
    active = active.loc[first:].iloc[1:]  # first month = the one after the first positions
    bench = bench_ret.reindex(active.index)
    if beta_window is not None:
        active = _hedge(active, bench, rf.reindex(active.index), beta_window)
    return pd.DataFrame({
        "active": active,
        "total": bench + active,  # equitized: index exposure through futures + the pocket
        "turnover": turnover.reindex(active.index),
    })
