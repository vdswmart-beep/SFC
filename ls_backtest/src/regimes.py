"""Market regimes (trend x volatility) for the conditional analysis (H4)."""
import numpy as np
import pandas as pd


def regimes(bench_ret: pd.Series) -> pd.Series:
    """Regime of each month, e.g. "Bull / high vol", known before the month starts.
    Input: monthly benchmark returns; output: Series of labels (NaN at the start)."""
    ret_12m = (1 + bench_ret).rolling(12).apply(np.prod, raw=True) - 1
    vol_12m = bench_ret.rolling(12).std()
    # expanding median: the volatility threshold only uses the past
    vol_median = vol_12m.expanding(min_periods=36).median()
    trend = pd.Series(np.where(ret_12m > 0, "Bull", "Bear"), index=bench_ret.index)
    vol = pd.Series(np.where(vol_12m > vol_median, "high vol", "low vol"), index=bench_ret.index)
    label = (trend + " / " + vol).where(ret_12m.notna() & vol_median.notna())
    # shifted by one month: the regime of month t is observed at the end of month t-1
    return label.shift(1)
