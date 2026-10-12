"""Raw signals, sector z-scores and composite score."""
import pandas as pd


def compute_signals(tr: pd.DataFrame, btp: pd.DataFrame, roe: pd.DataFrame,
                    fund_lag: int) -> dict[str, pd.DataFrame]:
    """Raw signals, oriented so that higher = more attractive.
    Inputs wide (dates x tickers); output: {signal name: wide DataFrame}."""
    ret = tr.pct_change(fill_method=None)
    return {
        # lagged fundamentals: at t, the accounts of the latest period are not yet published
        "value": btp.shift(fund_lag),
        # 12-1: the last month is skipped, it is dominated by short-term reversal
        "momentum": tr.shift(1) / tr.shift(12) - 1,
        "quality": roe.shift(fund_lag),
        # minus sign: low volatility is what we want
        "lowvol": -ret.rolling(36, min_periods=24).std(),
    }


def sector_zscore(raw: pd.DataFrame, member: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    """Z-score of a signal by sector and by date, computed on index members at t only.
    Inputs: signal and membership (1/0) wide, sectors ticker -> sector; output wide."""
    x = raw.where(member == 1)  # a non-member weighs neither on the mean nor on the std
    z = pd.DataFrame(index=raw.index, columns=raw.columns, dtype=float)
    for sector in sectors.dropna().unique():
        cols = raw.columns.intersection(sectors.index[sectors == sector])
        block = x[cols]  # dates x stocks of the sector
        # each row (date) is standardized on its own: a cross-sectional comparison
        z[cols] = block.sub(block.mean(axis=1), axis=0).div(block.std(axis=1), axis=0)
    # capped at +/-3: one outlier must not dominate the composite
    return z.clip(-3, 3)


def composite(zscores: dict[str, pd.DataFrame], min_signals: int) -> pd.DataFrame:
    """Equal-weighted mean of the available z-scores; NaN with fewer than min_signals signals.
    Input: {signal: z wide}; output: composite score wide."""
    n_available = sum(z.notna().astype(int) for z in zscores.values())
    total = sum(z.fillna(0) for z in zscores.values())
    return (total / n_available).where(n_available >= min_signals)
