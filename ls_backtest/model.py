"""The model in one call: data -> signals -> pairs -> the switch -> backtests -> tables.
Reads config.py; used by main.py (command line) and app.py (web app): both show the same results."""
import pandas as pd

import config
from src import report
from src.backtest import run_backtest
from src.metrics import ff_alpha
from src.portfolio import long_only_weights, ls_weights, skip_short_leg
from src.regimes import regimes
from src.signals import composite, compute_signals, sector_zscore

SMART_BETA = "Smart beta (long-only)"


def mode_name(long_only: bool) -> str:
    """Plain-English name of a mode, printed by main.py and shown by the web app."""
    if long_only:
        return "Long-only: the LONGs alone, fully invested, no hedge"
    return "Long/short: index + LONG/SHORT pocket" + (", beta-hedged" if config.BETA_HEDGE else "")


def ranking_score(name: str, z: dict, score: pd.DataFrame) -> pd.DataFrame:
    """The score that ranks the stocks of a strategy: its signal's z-score for a single-factor
    strategy, the composite score for the others."""
    return z.get(name.removeprefix("Single "), score)


def _hedge(name: str, long_only: bool) -> int | None:
    """Beta-hedge window of a strategy: only the long/short pockets are hedged (index futures)."""
    hedged = config.BETA_HEDGE and not long_only and name != SMART_BETA
    return config.BETA_WINDOW if hedged else None


def build_strategies(data: dict) -> tuple[dict, dict, dict, pd.DataFrame]:
    """LONG/SHORT weights of every tested strategy, plus the smart beta reference, and the signals
    behind them. Output: ({strategy: weights}, {signal: raw}, {signal: z-scores}, composite)."""
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
    return strategies, raw, z, score


def run_all(strategies: dict, data: dict, long_only: bool) -> dict[str, pd.DataFrame]:
    """Backtests every strategy on one common sample: from the latest start, and up to the
    hold-out when it is hidden. Output: {strategy: run_backtest output}."""
    returns = data["tr"].pct_change(fill_method=None)
    results = {}
    for name, weights in strategies.items():
        if not weights.to_numpy().any():  # e.g. no accounts: the signal never exists
            print(f"{name}: no position, strategy skipped")
            continue
        results[name] = run_backtest(weights, returns, data["bench_ret"], data["rf"],
                                     config.TC_BPS, config.BORROW_BPS_YR, _hedge(name, long_only))
    if not results:
        raise SystemExit("No strategy has positions: check the data.")
    start = max(res.index[0] for res in results.values())  # same start: comparable periods
    holdout = pd.Timestamp(config.HOLDOUT_START)
    end = None if config.SHOW_HOLDOUT else holdout - pd.DateOffset(days=1)  # last month shown
    results = {name: res.loc[start:end] for name, res in results.items()}
    if len(next(iter(results.values()))) < 2:
        raise SystemExit("Fewer than 2 months to evaluate: set SHOW_HOLDOUT = True in config.py.")
    return results


def build_tables(results: dict, strategies: dict, z: dict, score: pd.DataFrame, data: dict,
                 long_only: bool) -> dict[str, pd.DataFrame]:
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
        tables["Costs"] = report.cost_table(strategies[main], returns, bench, rf,
                                            _hedge(main, long_only), config.TC_GRID_BPS,
                                            config.BORROW_GRID_BPS_YR, results[main].index)
        tables["Positions"] = report.positions_table(strategies[main], score, z, data["sectors"])
    tables["Monthly returns"] = report.pocket_returns(results)
    return tables


def run_model(data: dict, long_only: bool) -> dict:
    """Runs the whole model on one data set; long_only is the switch. Output: a dict (a "run") with
    long_short = the pairs' weights, strategies = the weights held after the switch, and more."""
    long_short, raw, z, score = build_strategies(data)
    strategies = long_short
    if long_only:  # the switch: same LONGs, the SHORT leg is skipped (the smart beta has none)
        strategies = {name: skip_short_leg(w) for name, w in long_short.items()}
    results = run_all(strategies, data, long_only)
    curves = {name: results[name]["total"] for name in [config.MAIN_STRATEGY, SMART_BETA]
              if name in results}
    curves["Benchmark"] = data["bench_ret"].reindex(next(iter(results.values())).index)
    tables = build_tables(results, strategies, z, score, data, long_only)
    return {"long_only": long_only, "mode": mode_name(long_only), "sectors": data["sectors"],
            "raw": raw, "z": z, "score": score, "long_short": long_short,
            "strategies": strategies, "results": results, "curves": pd.DataFrame(curves),
            "tables": tables}
