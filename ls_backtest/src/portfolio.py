"""Portfolio weights: the best scores LONG and the worst SHORT, spread over the sectors, and the
long-only reference."""
import pandas as pd


def _pick(ranked: list[str], sector_of: dict[str, str], n: int, max_per_sector: int,
          allowed: set[str]) -> list[str]:
    """The first n allowed tickers of `ranked`, with at most max_per_sector of one sector."""
    chosen, per_sector = [], {}
    for ticker in ranked:
        sector = sector_of[ticker]
        if ticker in allowed and per_sector.get(sector, 0) < max_per_sector:
            chosen.append(ticker)
            per_sector[sector] = per_sector.get(sector, 0) + 1
        if len(chosen) == n:
            break
    return chosen


def _date_weights(scored: pd.Series, sector_of: dict[str, str], n_positions: int,
                  max_per_sector: int, long_ok: set[str], short_ok: set[str]) -> pd.Series:
    """Weights at one date: the n_positions / 2 best scores LONG, the n_positions / 2 worst
    SHORT, equally weighted: LONGs +100 %, SHORTs -100 %. Output: Series ticker -> weight."""
    best_first = scored.sort_values(ascending=False, kind="stable")
    # a LONG must score above its sector's average and a SHORT below: never the same stock
    ranked_long = best_first[best_first > 0].index.tolist()
    ranked_short = best_first[best_first < 0].index.tolist()[::-1]  # worst first
    longs = _pick(ranked_long, sector_of, n_positions // 2, max_per_sector, long_ok)
    shorts = _pick(ranked_short, sector_of, n_positions // 2, max_per_sector, short_ok)
    if not longs or not shorts:
        return pd.Series(dtype=float)  # one side missing: the pocket would not self-finance
    weights = {ticker: 1 / len(longs) for ticker in longs}
    weights.update({ticker: -1 / len(shorts) for ticker in shorts})
    return pd.Series(weights, dtype=float)


def _eligible(score: pd.DataFrame, zscores: dict[str, pd.DataFrame] | None,
              excl_threshold: float | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stocks allowed on the LONG and on the SHORT side; without exclusion, all of them.
    Output: two boolean masks, wide (dates x tickers)."""
    if zscores is None:
        everyone = pd.DataFrame(True, index=score.index, columns=score.columns)
        return everyone, everyone
    # a stock that is very poor on one factor is not bought even if its composite is good
    # (and symmetrically for the SHORT side)
    stacked = pd.concat(list(zscores.values()))  # z-scores of every signal, stacked
    z_min = stacked.groupby(level=0).min().reindex_like(score)  # worst z of the stock at t
    z_max = stacked.groupby(level=0).max().reindex_like(score)  # best z of the stock at t
    return z_min >= excl_threshold, z_max <= -excl_threshold


def ls_weights(score: pd.DataFrame, sectors: pd.Series, n_positions: int, max_per_sector: int,
               min_sector_size: int, min_stocks_date: int,
               zscores: dict[str, pd.DataFrame] | None = None,
               excl_threshold: float | None = None) -> pd.DataFrame:
    """LONG/SHORT weights: at each date, the best scores LONG and the worst SHORT, at most
    max_per_sector stocks of one sector on each side. Inputs: score wide (NaN = not scored),
    optional zscores for the exclusion variant; output: weights wide, LONGs +1, SHORTs -1."""
    long_ok, short_ok = _eligible(score, zscores, excl_threshold)
    sector_of = sectors.to_dict()  # a dict: much faster than a Series for one item at a time
    weights = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    for date in score.index:
        scored = score.loc[date].dropna()  # stocks with a score at this date
        if len(scored) < min_stocks_date:
            continue  # universe too thin: date not invested
        sector_size = scored.groupby(sectors).transform("size")
        scored = scored[sector_size >= min_sector_size]  # tiny sector: z-scores unreliable
        long_set = set(score.columns[long_ok.loc[date]])  # tickers allowed on the LONG side
        short_set = set(score.columns[short_ok.loc[date]])
        w = _date_weights(scored, sector_of, n_positions, max_per_sector, long_set, short_set)
        weights.loc[date, w.index] = w.to_numpy()
    return weights


def skip_short_leg(weights: pd.DataFrame) -> pd.DataFrame:
    """Long-only version of a LONG/SHORT portfolio: the SHORT leg is dropped. The LONGs already
    sum to 100 %, so the portfolio stays fully invested in exactly the same stocks."""
    return weights.clip(lower=0)


def long_only_weights(score: pd.DataFrame, top: float, min_stocks_date: int) -> pd.DataFrame:
    """Smart beta reference: the best `top` fraction of scored stocks, equally weighted.
    Input: score wide (NaN = not scored); output: weights wide, summing to 1 at each date."""
    weights = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    for date in score.index:
        scored = score.loc[date].dropna()
        if len(scored) < min_stocks_date:
            continue  # universe too thin: date not invested
        best = scored.sort_values(ascending=False, kind="stable").index
        n = max(1, round(top * len(scored)))
        weights.loc[date, best[:n]] = 1 / n
    return weights
