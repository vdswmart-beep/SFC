"""Reads the model's CSV files, and generates fake data in the same format."""
from pathlib import Path

import numpy as np
import pandas as pd

FACTOR_NAMES = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "WML"]


def _read_wide(path: Path) -> pd.DataFrame:
    """Reads a CSV whose first column is a date; the dates are moved to calendar month-ends."""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    # sources stamp month-end data on the last business day: calendar month-ends align all files
    df.index = df.index + pd.offsets.MonthEnd(0)
    return df.sort_index()


def load_data(folder: str) -> dict:
    """Loads the CSV files of `folder` (format in README section 4).
    Output: dict tr, btp, roe, member, sectors, bench_ret, rf, factors (None if absent)."""
    path = Path(folder)
    tr = _read_wide(path / "tr_index.csv")
    # one dates x tickers grid for every file: avoids silent misalignments between files
    btp, roe, member = (_read_wide(path / name).reindex(index=tr.index, columns=tr.columns)
                        for name in ["book_to_price.csv", "roe.csv", "member.csv"])
    bench = _read_wide(path / "bench.csv")
    factors_path = path / "factors.csv"
    return {
        "tr": tr,
        "btp": btp,
        "roe": roe,
        "member": member.fillna(0),  # ticker missing from the file = not a member
        "sectors": pd.read_csv(path / "sector.csv", index_col="ticker")["sector"],
        "bench_ret": bench["bench"].pct_change(fill_method=None).reindex(tr.index),
        # a missing rate keeps the last known one: a gap must not wipe out a month of results
        "rf": (bench["rf"] / 100 / 12).reindex(tr.index).ffill().fillna(0.0),
        "factors": _read_wide(factors_path) / 100 if factors_path.exists() else None,
    }


def make_fake_data(n_stocks: int = 800, start: str = "2005-01-31", end: str = "2025-12-31",
                   seed: int = 0) -> dict:
    """Synthetic data in the format of load_data, with no factor premium at all:
    apart from costs and residual beta, every strategy should show an IR close to 0."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="ME")
    tickers = [f"STOCK{i:03d}" for i in range(n_stocks)]
    shape = (len(dates), n_stocks)
    mkt = rng.normal(0.006, 0.045, len(dates))
    ret = mkt[:, None] * rng.uniform(0.5, 1.5, n_stocks) + rng.normal(0, 0.07, shape)
    # one random entry and exit per stock: the universe changes over time
    t = np.arange(len(dates))[:, None]
    entry = rng.integers(-len(dates), len(dates), n_stocks)
    exit_ = rng.integers(0, 3 * len(dates), n_stocks)
    arrays = {
        "tr": 100 * np.cumprod(1 + ret, axis=0),
        "btp": np.exp(rng.normal(-0.7, 0.5, n_stocks) + rng.normal(0, 0.1, shape)),
        "roe": rng.normal(0.12, 0.08, n_stocks) + rng.normal(0, 0.02, shape),
        "member": ((t >= entry) & (t < exit_)).astype(int),
    }
    data = {k: pd.DataFrame(v, index=dates, columns=tickers) for k, v in arrays.items()}
    rf = pd.Series(0.02 / 12, index=dates)
    factors = pd.DataFrame(rng.normal(0, 0.02, (len(dates), 6)), index=dates, columns=FACTOR_NAMES)
    factors["Mkt-RF"] = mkt - rf
    sector_ids = rng.integers(0, 11, n_stocks)  # 11 sectors, like the GICS classification
    data["sectors"] = pd.Series([f"SECTOR{k:02d}" for k in sector_ids], index=tickers)
    data.update(bench_ret=pd.Series(mkt, index=dates), rf=rf, factors=factors)
    return data
