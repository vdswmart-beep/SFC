"""Portfolio weights: LONG/SHORT pairs taken within one sector, and the long-only reference."""
import pandas as pd


def _sector_pairs(sector_scores: pd.Series, long_ok: set[str],
                  short_ok: set[str]) -> list[tuple[float, str, str]]:
    """Candidate pairs of a sector: best vs worst score, then 2nd best vs 2nd worst, etc.
    Output: list of (score spread, LONG ticker, SHORT ticker)."""
    # plain list and dict: much faster than pandas objects when read one item at a time
    best_first = sector_scores.sort_values(ascending=False, kind="stable").index.tolist()
    score = sector_scores.to_dict()
    longs = [t for t in best_first if t in long_ok]  # exclusion variant (otherwise all pass)
    shorts = [t for t in reversed(best_first) if t in short_ok]
    pairs = []
    for long, short in zip(longs, shorts, strict=False):  # lengths differ with the exclusion
        spread = score[long] - score[short]
        if spread <= 0:
            break  # the two lists have crossed: no useful pair left in this sector
        pairs.append((spread, long, short))
    return pairs


def _date_weights(scored: pd.Series, sectors: pd.Series, n_positions: int, min_sector_size: int,
                  long_ok: set[str], short_ok: set[str]) -> pd.Series:
    """Weights at one date: the n_positions / 2 pairs with the widest score spread.
    Input: scores of the scored stocks, tickers allowed on each side; output: ticker -> weight."""
    candidates = []
    for _, sector_scores in scored.groupby(sectors):
        if len(sector_scores) >= min_sector_size:  # too few stocks: unreliable comparison
            candidates += _sector_pairs(sector_scores, long_ok, short_ok)
    chosen = sorted(candidates, reverse=True)[: n_positions // 2]  # widest spreads first
    total_spread = sum(spread for spread, _, _ in chosen)
    weights = {}
    for spread, long, short in chosen:
        # a wider spread is a stronger conviction, hence a bigger pair; the LONG and the SHORT
        # of a pair weigh the same, so every sector nets to 0 (LONGs +100 %, SHORTs -100 %)
        weights[long] = spread / total_spread
        weights[short] = -spread / total_spread
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


def ls_weights(score: pd.DataFrame, sectors: pd.Series, n_positions: int, min_sector_size: int,
               min_stocks_date: int, zscores: dict[str, pd.DataFrame] | None = None,
               excl_threshold: float | None = None) -> pd.DataFrame:
    """LONG/SHORT weights: at each date, n_positions / 2 pairs (1 LONG + 1 SHORT of a sector).
    Inputs: score wide (NaN = not scored), optional zscores for the exclusion variant;
    output: weights wide; LONGs = +1, SHORTs = -1, every sector nets to 0."""
    long_ok, short_ok = _eligible(score, zscores, excl_threshold)
    weights = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    for date in score.index:
        scored = score.loc[date].dropna()  # stocks with a score at this date
        if len(scored) < min_stocks_date:
            continue  # universe too thin: date not invested
        long_set = set(score.columns[long_ok.loc[date]])  # tickers allowed on the LONG side
        short_set = set(score.columns[short_ok.loc[date]])
        w = _date_weights(scored, sectors, n_positions, min_sector_size, long_set, short_set)
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
