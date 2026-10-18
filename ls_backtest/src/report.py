"""Result tables (pure functions): performance, Sharpe test, regimes, stress, costs, positions."""
import numpy as np
import pandas as pd

from src.backtest import run_backtest
from src.metrics import perf_stats, sharpe_test


def pocket_returns(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Monthly active (pocket) returns of every strategy, one column per strategy."""
    return pd.DataFrame({name: res["active"] for name, res in results.items()}).rename_axis("Month")


def summary_table(results: dict[str, pd.DataFrame], bench_ret: pd.Series,
                  rf: pd.Series) -> pd.DataFrame:
    """Performance statistics of each strategy.
    Input: {name: run_backtest output}; output: DataFrame strategies x statistics."""
    table = pd.DataFrame({name: perf_stats(res, bench_ret, rf) for name, res in results.items()})
    return table.T.rename_axis("Strategy")


def sharpe_table(results: dict[str, pd.DataFrame], bench_ret: pd.Series, rf: pd.Series,
                 alpha: float) -> pd.DataFrame:
    """One-sided Sharpe test of each strategy's total portfolio against the benchmark."""
    table = pd.DataFrame({name: sharpe_test(res["total"], bench_ret, rf)
                          for name, res in results.items()}).T
    table[f"Significant at {alpha:.0%}"] = np.where(table["p-value"] < alpha, "Yes", "No")
    return table.rename_axis("Strategy")


def regime_table(results: dict[str, pd.DataFrame], regime: pd.Series) -> pd.DataFrame:
    """Months and IR of each strategy in each market regime (H4)."""
    active = pocket_returns(results)
    by_regime = active.groupby(regime.reindex(active.index))
    table = by_regime.mean() / by_regime.std() * np.sqrt(12)
    table.insert(0, "Months", by_regime.size())
    return table.rename_axis("Regime")


def stress_table(results: dict[str, pd.DataFrame], bench_ret: pd.Series,
                 periods: dict[str, tuple[str, str]]) -> pd.DataFrame:
    """Cumulative return of the benchmark and of each pocket over each stress period.
    A period outside the sample shows NaN."""
    returns = pocket_returns(results)
    returns.insert(0, "Benchmark", bench_ret.reindex(returns.index))
    table = {label: (1 + returns.loc[start:end]).prod(min_count=1) - 1
             for label, (start, end) in periods.items()}
    return pd.DataFrame(table).T.rename_axis("Stress period")


def cost_table(weights: pd.DataFrame, returns: pd.DataFrame, bench_ret: pd.Series,
               rf: pd.Series, beta_window: int | None, tc_grid: list[float],
               borrow_grid: list[float], sample: pd.DatetimeIndex) -> pd.DataFrame:
    """IR of one strategy under each pair of cost assumptions (H3 sensitivity).
    Output: transaction costs in rows, borrow fees in columns, measured over `sample`."""
    table = pd.DataFrame(index=[f"TC {tc} bps" for tc in tc_grid], dtype=float,
                         columns=[f"Borrow {fee} bps/yr" for fee in borrow_grid])
    for tc in tc_grid:
        for fee in borrow_grid:
            res = run_backtest(weights, returns, bench_ret, rf, tc, fee, beta_window).loc[sample]
            ir = perf_stats(res, bench_ret, rf)["IR"]
            table.loc[f"TC {tc} bps", f"Borrow {fee} bps/yr"] = ir
    return table.rename_axis("IR")


def positions_table(weights: pd.DataFrame, score: pd.DataFrame, zscores: dict[str, pd.DataFrame],
                    sectors: pd.Series, date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Positions at `date` (default: the last invested date): side, weight, sector, score and
    factor z-scores. Output: one row per position, LONGs first, largest weights first."""
    if date is None:
        date = weights.index[weights.abs().sum(axis=1) > 0][-1]
    held = weights.loc[date][weights.loc[date] != 0]
    held = pd.concat([held[held > 0].sort_values(ascending=False), held[held < 0].sort_values()])
    table = pd.DataFrame({"Date": date, "Side": np.where(held > 0, "LONG", "SHORT"),
                          "Weight": held, "Sector": sectors.reindex(held.index),
                          "Score": score.loc[date, held.index]})
    for name, z in zscores.items():
        table[f"z {name}"] = z.loc[date, held.index]
    return table.rename_axis("Ticker")
