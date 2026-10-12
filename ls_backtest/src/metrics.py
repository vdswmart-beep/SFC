"""Performance measures: annualized statistics, Sharpe test and multi-factor alpha."""
from math import erf, sqrt

import pandas as pd
import statsmodels.api as sm


def _sharpe(excess: pd.Series) -> float:
    """Annualized Sharpe ratio of a monthly excess-return series."""
    return excess.mean() / excess.std() * sqrt(12)


def perf_stats(res: pd.DataFrame, bench_ret: pd.Series, rf: pd.Series) -> pd.Series:
    """Annualized statistics of one strategy.
    Inputs: run_backtest output, monthly Series; output: Series name -> value."""
    active, bench, rf = res["active"], bench_ret.reindex(res.index), rf.reindex(res.index)
    ann, te = active.mean() * 12, active.std() * sqrt(12)
    wealth = (1 + active).cumprod()
    return pd.Series({
        "Active return (ann.)": ann,
        "Tracking error": te,
        # the pocket is self-financing (already an excess return): its Sharpe ratio is its IR
        "IR (pocket Sharpe)": ann / te,
        "t-stat": active.mean() / active.std() * sqrt(len(active)),
        "Max DD (pocket)": (wealth / wealth.cummax() - 1).min(),
        "Pocket beta": active.cov(bench) / bench.var(),  # close to 0 when the hedge works
        "Avg turnover": res["turnover"].mean(),
        "Sharpe (total)": _sharpe(res["total"] - rf),
        "Sharpe (benchmark)": _sharpe(bench - rf),
    })


def sharpe_test(total: pd.Series, bench_ret: pd.Series, rf: pd.Series) -> pd.Series:
    """Jobson-Korkie test with Memmel's (2003) correction: is the strategy's Sharpe ratio above
    the benchmark's? Inputs: monthly returns; output: Sharpe ratios, z and one-sided p-value."""
    rf = rf.reindex(total.index)
    a, b = total - rf, bench_ret.reindex(total.index) - rf
    sr_a, sr_b, rho = a.mean() / a.std(), b.mean() / b.std(), a.corr(b)
    variance = (2 * (1 - rho) + 0.5 * (sr_a**2 + sr_b**2 - 2 * sr_a * sr_b * rho**2)) / len(a)
    z = (sr_a - sr_b) / sqrt(variance)
    return pd.Series({
        "Sharpe (total)": sr_a * sqrt(12),
        "Sharpe (benchmark)": sr_b * sqrt(12),
        "z (JKM)": z,
        "p-value": 0.5 * (1 - erf(z / sqrt(2))),  # P(Z > z): H0 = equal Sharpe ratios
    })


def ff_alpha(active: pd.Series, factors: pd.DataFrame, maxlags: int) -> pd.Series:
    """Annualized alpha of the pocket against the factors (OLS, Newey-West HAC errors).
    Monthly inputs in decimals; output: Series [Alpha (ann.), t-stat alpha]."""
    # the pocket is self-financing: already an excess return, no rf to subtract
    exog = sm.add_constant(factors.reindex(active.index))
    fit = sm.OLS(active, exog, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    alpha, t_stat = fit.params["const"] * 12, fit.tvalues["const"]
    return pd.Series({"Alpha (ann.)": alpha, "t-stat alpha": t_stat})
