"""Plain-English explanations of a portfolio, for the web app: pairs, reasons, ranking, changes."""
import numpy as np
import pandas as pd

# each signal in words, when its z-score is positive / negative
WORDS = {"value": ("cheap", "expensive"), "momentum": ("rising", "falling"),
         "quality": ("profitable", "unprofitable"), "lowvol": ("steady", "volatile")}


def pairs_at(long_short: pd.Series, score: pd.Series, sectors: pd.Series) -> pd.DataFrame:
    """The LONG/SHORT pairs at one date, rebuilt from the weights: in each sector the best LONG
    faces the worst SHORT, the 2nd best the 2nd worst... (as in portfolio.py).
    Inputs: weights and scores at that date; output: one row per pair, widest spread first."""
    held = long_short[long_short != 0]
    rows = []
    for sector, w in held.groupby(sectors.reindex(held.index)):
        longs = score[w.index[w > 0]].sort_values(ascending=False, kind="stable").index
        shorts = score[w.index[w < 0]].sort_values(kind="stable").index
        for long, short in zip(longs, shorts, strict=True):  # every LONG has its SHORT
            rows.append({"Sector": sector, "LONG": long, "SHORT": short,
                         "Spread": score[long] - score[short], "Weight": held[long]})
    pairs = pd.DataFrame(rows, columns=["Sector", "LONG", "SHORT", "Spread", "Weight"])
    pairs = pairs.sort_values("Spread", ascending=False, ignore_index=True)
    return pairs.set_axis(pd.RangeIndex(1, len(pairs) + 1, name="Pair"))


def _word(signal: str, z: float) -> str:
    """One signal in words, e.g. 'cheap (+1.8)' or 'expensive (-1.2)'."""
    good, bad = WORDS.get(signal, (f"high {signal}", f"low {signal}"))  # a new signal: plain
    return f"{good if z > 0 else bad} ({z:+.1f})"


def why(z: pd.Series, side: str) -> str:
    """Why a stock sits on its side, in words: the signals for it (|z| >= 0.5), strongest first,
    then the signals against it (|z| >= 1). Input: the stock's z-score by signal."""
    signed = z.dropna() * (1 if side == "LONG" else -1)  # > 0: the signal supports the side
    pros = [_word(k, z[k]) for k in signed[signed >= 0.5].sort_values(ascending=False).index]
    cons = [_word(k, z[k]) for k in signed[signed <= -1].sort_values().index]
    text = ", ".join(pros) or "no single strong signal"
    return text + ("; but " + ", ".join(cons) if cons else "")


def with_reasons(lines: pd.DataFrame) -> pd.DataFrame:
    """A positions table (report.positions_table) with a 'Why' column, in words."""
    z = lines.filter(regex="^z ").rename(columns=lambda column: column.removeprefix("z "))
    return lines.assign(Why=[why(z.loc[ticker], side) for ticker, side in lines["Side"].items()])


def ranking_at(date: pd.Timestamp, score: pd.DataFrame, zscores: dict[str, pd.DataFrame],
               sectors: pd.Series, weights: pd.DataFrame) -> pd.DataFrame:
    """Every scored stock at one date, best score first: rank, sector, rank in its sector, score,
    z-scores, and the side and weight held (blank when not held)."""
    best_first = score.loc[date].dropna().sort_values(ascending=False, kind="stable")
    table = pd.DataFrame({"Rank": np.arange(1, len(best_first) + 1),
                          "Sector": sectors.reindex(best_first.index), "Score": best_first})
    # pairs are formed inside a sector: the rank there says who can be LONG or SHORT
    in_sector = table.groupby("Sector")["Score"].rank(ascending=False, method="first")
    table["Rank in sector"] = in_sector.astype(int)
    for name, z in zscores.items():
        table[f"z {name}"] = z.loc[date, best_first.index]
    held = weights.loc[date, best_first.index]
    table["Side"] = np.select([held > 0, held < 0], ["LONG", "SHORT"], default="")
    table["Weight"] = held.where(held != 0)
    return table.rename_axis("Ticker")


def holdings(weights: pd.DataFrame, sectors: pd.Series, end: pd.Timestamp,
             months: int) -> pd.DataFrame:
    """The positions of the last `months` month-ends up to `end`, one row per (month, stock)
    held: Month, Ticker, Weight, Sector, Side. Feeds the holdings heatmap."""
    window = weights.loc[:end].tail(months).rename_axis("Month").reset_index()
    cells = window.melt(id_vars="Month", var_name="Ticker", value_name="Weight")
    cells = cells[cells["Weight"] != 0]
    return cells.assign(Month=cells["Month"].dt.strftime("%Y-%m"),
                        Sector=cells["Ticker"].map(sectors),
                        Side=np.where(cells["Weight"] > 0, "LONG", "SHORT"))


def moves(weights: pd.DataFrame, date: pd.Timestamp) -> tuple[list[str], list[str]]:
    """Tickers that entered and that left the portfolio at `date`, versus the month before."""
    position = weights.index.get_loc(date)
    now = weights.iloc[position] != 0
    before = weights.iloc[position - 1] != 0 if position > 0 else pd.Series(False, now.index)
    return now.index[now & ~before].tolist(), now.index[before & ~now].tolist()
