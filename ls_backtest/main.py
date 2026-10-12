"""Orchestration: data -> signals -> weights -> backtests -> tables -> outputs."""
import sys

import pandas as pd

import config
from src import report
from src.backtest import run_backtest
from src.charts import performance_charts
from src.data import load_data, make_fake_data
from src.export import save_outputs
from src.metrics import ff_alpha
from src.portfolio import long_only_weights, ls_weights
from src.regimes import regimes
from src.signals import composite, compute_signals, sector_zscore

SMART_BETA = "Smart beta (long-only)"


def _hedge(name: str) -> int | None:
    """Beta-hedge window of a strategy; the long-only reference is never hedged."""
    return config.BETA_WINDOW if config.BETA_HEDGE and name != SMART_BETA else None


def build_strategies(data: dict) -> tuple[dict, dict, pd.DataFrame]:
    """Weights of every tested strategy, plus the z-scores and the composite score behind them.
    Output: ({strategy: weights}, {signal: z-scores}, composite score), all wide."""
    raw = compute_signals(data["tr"], data["btp"], data["roe"], config.FUND_LAG)
    z = {k: sector_zscore(raw[k], data["member"], data["sectors"]) for k in config.SIGNALS}
    score = composite(z, config.MIN_SIGNALS)
    params = dict(sectors=data["sectors"], n_positions=config.N_POSITIONS,
                  min_sector_size=config.MIN_SECTOR_SIZE, min_stocks_date=config.MIN_STOCKS_DATE)
    strategies = {f"Single {k}": ls_weights(z[k], **params) for k in config.SIGNALS}
    strategies["Composite"] = ls_weights(score, **params)
    strategies["Composite + exclusion"] = ls_weights(score, **params, zscores=z,
                                                     excl_threshold=config.EXCL_THRESHOLD)
    strategies[SMART_BETA] = long_only_weights(score, config.SMART_BETA_TOP,
                                               config.MIN_STOCKS_DATE)
    return strategies, z, score


def run_all(strategies: dict[str, pd.DataFrame], data: dict) -> dict[str, pd.DataFrame]:
    """Backtests every strategy on one common sample: from the latest start, and up to the
    hold-out when it is hidden. Output: {strategy: run_backtest output}."""
    returns = data["tr"].pct_change(fill_method=None)
    results = {}
    for name, weights in strategies.items():
        if not weights.to_numpy().any():  # e.g. no accounts: the signal never exists
            print(f"{name}: no position, strategy skipped")
            continue
        results[name] = run_backtest(weights, returns, data["bench_ret"], data["rf"],
                                     config.TC_BPS, config.BORROW_BPS_YR, _hedge(name))
    if not results:
        raise SystemExit("No strategy has positions: check the data.")
    start = max(res.index[0] for res in results.values())  # same start: comparable periods
    holdout = pd.Timestamp(config.HOLDOUT_START)
    end = None if config.SHOW_HOLDOUT else holdout - pd.DateOffset(days=1)  # last month shown
    results = {name: res.loc[start:end] for name, res in results.items()}
    if len(next(iter(results.values()))) < 2:
        raise SystemExit("Fewer than 2 months to evaluate: set SHOW_HOLDOUT = True in config.py.")
    return results


def build_tables(results: dict, strategies: dict, z: dict, score: pd.DataFrame,
                 data: dict) -> dict[str, pd.DataFrame]:
    """Every result table, keyed by its title (also its Excel sheet name)."""
    bench, rf, holdout = data["bench_ret"], data["rf"], pd.Timestamp(config.HOLDOUT_START)
    periods = {"Full sample": results}
    if config.SHOW_HOLDOUT:  # hidden hold-out: the full sample already stops before it
        periods[f"Before {holdout:%Y}"] = {k: r[r.index < holdout] for k, r in results.items()}
        periods[f"Hold-out {holdout:%Y}+"] = {k: r[r.index >= holdout] for k, r in results.items()}
    summaries = {title: report.summary_table(res, bench, rf) for title, res in periods.items()
                 if all(len(r) > 1 for r in res.values())}  # a period without data is skipped
    tables = {"Summary": pd.concat(summaries, names=["Period", "Strategy"]),
              "Sharpe test": report.sharpe_table(results, bench, rf, config.SIGNIFICANCE)}
    if data["factors"] is not None:
        alphas = {k: ff_alpha(r["active"], data["factors"], config.NW_LAGS)
                  for k, r in results.items()}
        tables["Alpha"] = pd.DataFrame(alphas).T.rename_axis("Strategy")
    tables["Regimes"] = report.regime_table(results, regimes(bench))
    tables["Stress tests"] = report.stress_table(results, bench, config.STRESS_PERIODS)
    main = config.MAIN_STRATEGY
    if main in results:
        returns = data["tr"].pct_change(fill_method=None)
        tables["Costs"] = report.cost_table(strategies[main], returns, bench, rf, _hedge(main),
                                            config.TC_GRID_BPS, config.BORROW_GRID_BPS_YR,
                                            results[main].index)
        tables["Positions"] = report.positions_table(strategies[main], score, z, data["sectors"])
    tables["Monthly returns"] = report.pocket_returns(results)
    return tables


def main(folder: str | None = None) -> dict[str, pd.DataFrame]:
    """Runs the backtests, prints the tables and writes the outputs.
    Input: folder of CSV files (None = fake data); output: {strategy: run_backtest output}."""
    data = load_data(folder) if folder else make_fake_data()
    strategies, z, score = build_strategies(data)
    results = run_all(strategies, data)
    tables = build_tables(results, strategies, z, score, data)
    for title, table in tables.items():
        if title != "Monthly returns":  # too long for the console: see the Excel report
            print(f"\n=== {title} ===\n" + table.to_string(float_format="{:.3f}".format))
    curves = {name: results[name]["total"] for name in [config.MAIN_STRATEGY, SMART_BETA]
              if name in results}
    curves["Benchmark"] = data["bench_ret"].reindex(next(iter(results.values())).index)
    save_outputs(tables, performance_charts(pd.DataFrame(curves)), config.OUTPUT_DIR)
    print(f"\nCSV tables, report.xlsx and charts written to {config.OUTPUT_DIR}/")
    return results


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
