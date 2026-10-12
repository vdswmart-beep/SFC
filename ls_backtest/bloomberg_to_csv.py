"""Bloomberg connector: converts the refreshed extraction workbook into the model's CSV files.

The workbook is bloomberg/SXXP_extraction.xlsx (step-by-step instructions in its README sheet).
Save the refreshed copy in data/bloomberg/, then run from ls_backtest/:
    python bloomberg_to_csv.py data/bloomberg/SXXP_extraction.xlsx
The CSV files are written next to the workbook; then: python main.py data/bloomberg
Without dynamic arrays in Excel, `--universe` writes the member list to paste in Universe!A2.
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

MIN_MEMBERS = 590  # a month-end with fewer members was not fully loaded by Bloomberg


def _month_ends(values: pd.Series) -> pd.Series:
    """Excel dates (datetimes, or serial numbers in cells without a date format) -> month-ends."""
    is_date = values.map(lambda value: isinstance(value, datetime))
    serial = pd.to_numeric(values.where(~is_date), errors="coerce").dropna()
    from_serial = pd.to_datetime(serial, unit="D", origin="1899-12-30")  # 38383 -> 2005-01-31
    return pd.to_datetime(values.where(is_date)).fillna(from_serial) + pd.offsets.MonthEnd(0)


def _equity(member: str) -> str:
    """Bloomberg security of an index member: 'ASML NA' -> 'ASML NA Equity'."""
    member = member.strip()
    return member if member.endswith(" Equity") else f"{member} Equity"


def read_members(path: Path) -> pd.DataFrame:
    """Reads the Members sheet: a month-end in column A, that month's members below it in
    column B. Output: 1/0 DataFrame (month-ends x Bloomberg tickers)."""
    raw = pd.read_excel(path, sheet_name="Members", header=None, usecols="A:B").iloc[1:]
    dates = _month_ends(raw[0])
    names = raw[1].where(dates.isna())  # on a date row, column B holds the count, not a member
    is_member = names.map(lambda v: isinstance(v, str) and not v.startswith("#")
                          and v != "Index Member")  # Bloomberg errors and header excluded
    month = dates.ffill()[is_member].rename("month")  # the last month-end above each member
    tickers = names[is_member].map(_equity).rename("ticker")
    return pd.crosstab(month, tickers).clip(upper=1).rename_axis(index=None, columns=None)


def read_blocks(path: Path, sheet: str) -> pd.DataFrame:
    """Reads a sheet of BDH blocks: security in row 1, dates and values from row 4, two columns
    per security. Output: wide DataFrame (month-ends x securities)."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    blocks = {}
    for col in range(0, raw.shape[1] - 1, 2):
        name = raw.iat[0, col]
        if not isinstance(name, str) or not name.strip():
            continue  # empty slot, or download switched OFF
        values = pd.to_numeric(raw.iloc[3:, col + 1], errors="coerce")
        dates = _month_ends(raw.iloc[3:, col]).to_numpy()
        block = pd.Series(values.to_numpy(), index=dates).dropna()
        block = block[block.index.notna() & ~block.index.duplicated(keep="last")]
        if len(block):
            blocks[name.strip()] = block
    return pd.DataFrame(blocks).sort_index()


def _report(members: pd.DataFrame, tr: pd.DataFrame, sectors: pd.DataFrame) -> None:
    """Prints the checks to read before trusting the data (survivorship and coverage)."""
    complete = (members.sum(axis=1) >= MIN_MEMBERS).sum()
    no_tr = members.columns.difference(tr.columns)
    held = members.reindex(index=tr.index, columns=tr.columns, fill_value=0) == 1
    print(f"Month-ends with members: {len(members)} ({complete} with {MIN_MEMBERS}+ members)")
    print(f"Stocks ever in the index: {members.shape[1]}, without TR data: {len(no_tr)}"
          + (f" (e.g. {', '.join(no_tr[:5])})" if len(no_tr) else ""))
    print(f"Member-months without a TR value: {(held & tr.isna()).to_numpy().sum()}")
    print(f"Stocks with TR data but no sector: {len(tr.columns.difference(sectors['ticker']))}")


def main(workbook: str) -> None:
    """Reads the refreshed workbook and writes the 6 CSV files read by load_data (src/data.py)."""
    path = Path(workbook)
    print(f"Reading {path.name} (a few minutes for the STOXX Europe 600)...")
    tr = read_blocks(path, "TR")
    bench = read_blocks(path, "Benchmark").reindex(tr.index)
    if tr.empty or bench.shape[1] < 2:
        raise SystemExit("TR or Benchmark sheet without data: see the README sheet, steps 3-6.")
    grid = dict(index=tr.index, columns=tr.columns)
    pb, roe = (read_blocks(path, sheet).reindex(**grid) for sheet in ["PB", "ROE"])
    members = read_members(path)
    sectors = pd.read_excel(path, sheet_name="Universe", usecols="B,D")  # Ticker, GICS sector
    sectors = sectors.set_axis(["ticker", "sector"], axis=1).replace("", float("nan")).dropna()
    files = {
        "tr_index.csv": tr,
        "book_to_price.csv": 1 / pb.where(pb > 0),  # B/P = 1 / (P/B); no value if book <= 0
        "roe.csv": roe / 100,  # Bloomberg gives the ROE in percent
        "member.csv": members.reindex(**grid, fill_value=0),
        "bench.csv": pd.DataFrame({"bench": bench.iloc[:, 0], "rf": bench.iloc[:, 1]}),
    }
    for name, table in files.items():
        table.rename_axis("date").to_csv(path.parent / name)
    sectors.to_csv(path.parent / "sector.csv", index=False)
    _report(members, tr, sectors)
    print(f"6 files written to {path.parent}/: next, python main.py {path.parent}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "--universe":  # fallback for Excel without dynamic arrays (README sheet)
        names = read_members(Path(sys.argv[2])).columns.str.removesuffix(" Equity")
        pd.Series(names, name="Member").to_csv(Path(sys.argv[2]).parent / "universe.csv",
                                               index=False)
        print(f"{len(names)} members written to universe.csv: paste them in Universe!A2")
    else:
        main(sys.argv[1])
