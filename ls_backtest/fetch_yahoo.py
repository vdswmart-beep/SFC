"""Yahoo Finance connector: downloads the EURO STOXX 50 and writes the CSV files of data/yahoo/.

Phase 1 source (free, limited: README section 4). The model only reads the CSV files, so the
Bloomberg connector (bloomberg_to_csv.py) can replace this file without touching anything else.
Usage: python fetch_yahoo.py   then   python main.py data/yahoo
"""
from pathlib import Path

import pandas as pd
import yfinance as yf

START = "2005-01-01"  # start of the price history
BENCHMARK = "^STOXX50E"  # EURO STOXX 50 price index: Yahoo has no dividend-reinvested version
RF_PCT = 0.0  # annual risk-free rate in %: Yahoo has no 1-month EUR rate
OUT_DIR = Path("data/yahoo")
# Composition at 21/09/2026 (annual September review), by GICS sector: update at each review.
# Suffix = exchange: .DE Xetra, .PA Paris, .AS Amsterdam, .MI Milan, .MC Madrid,
# .BR Brussels, .HE Helsinki.
UNIVERSE = {
    "Communication Services": ["DTE.DE"],
    "Consumer Discretionary": ["ADS.DE", "BMW.DE", "ITX.MC", "MBG.DE", "MC.PA", "PRX.AS",
                               "RACE.MI", "RMS.PA"],
    "Consumer Staples": ["ABI.BR", "AD.AS", "BN.PA", "OR.PA"],
    "Energy": ["ENI.MI", "TTE.PA"],
    "Financials": ["ADYEN.AS", "ALV.DE", "BBVA.MC", "BNP.PA", "CS.PA", "DB1.DE", "DBK.DE",
                   "INGA.AS", "ISP.MI", "MUV2.DE", "NDA-FI.HE", "SAN.MC", "UCG.MI"],
    "Health Care": ["ARGX.BR", "BAYN.DE", "EL.PA", "SAN.PA"],
    "Industrials": ["AIR.PA", "DG.PA", "DHL.DE", "ENR.DE", "RHM.DE", "SAF.PA", "SGO.PA",
                    "SIE.DE", "SU.PA"],
    "Information Technology": ["ASML.AS", "IFX.DE", "NOKIA.HE", "SAP.DE"],
    "Materials": ["AI.PA", "BAS.DE"],
    "Utilities": ["ENEL.MI", "ENGI.PA", "IBE.MC"],
}


def download_prices(tickers: list[str], start: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily Yahoo prices reduced to the last trading day of each month.
    Output: (prices adjusted for dividends = total return index, raw prices), wide."""
    daily = yf.download(tickers, start=start, auto_adjust=False, progress=False)
    if daily.empty:
        raise SystemExit("No price received: check the connection to Yahoo Finance.")
    monthly = daily.resample("ME").last()
    monthly = monthly[monthly.index <= daily.index[-1]]  # drops the current, incomplete month
    return monthly["Adj Close"], monthly["Close"]


def _first_row(statement: pd.DataFrame, names: list[str]) -> pd.Series:
    """First line found among equivalent labels (they vary between companies)."""
    for name in names:
        if name in statement.index:
            return statement.loc[name]
    return pd.Series(dtype=float)


def download_accounts(ticker: str) -> pd.DataFrame:
    """Annual accounts of one stock: Yahoo only keeps the last 4 fiscal years.
    Output: DataFrame indexed by fiscal year end [book_per_share, roe]."""
    company = yf.Ticker(ticker)
    balance, income = company.balance_sheet, company.income_stmt
    equity = _first_row(balance, ["Common Stock Equity", "Stockholders Equity"])
    equity = equity.where(equity > 0)  # negative equity: the ratios are meaningless
    shares = _first_row(balance, ["Ordinary Shares Number", "Share Issued"])
    net_income = _first_row(income, ["Net Income Common Stockholders", "Net Income"])
    accounts = pd.DataFrame({"book_per_share": equity / shares, "roe": net_income / equity})
    info = company.info
    if info.get("financialCurrency") != info.get("currency"):
        # accounts in another currency than the price (e.g. USD): B/P would be wrong, dropped
        accounts["book_per_share"] = float("nan")
    return accounts.sort_index()


def to_month_ends(values: pd.DataFrame, month_ends: pd.DatetimeIndex) -> pd.DataFrame:
    """Value in force at each month-end: a fiscal year applies until the next year end.
    The publication delay is added later by the model (FUND_LAG in config.py)."""
    all_dates = values.index.union(month_ends)
    return values.reindex(all_dates).ffill().reindex(month_ends)


def main() -> None:
    """Downloads the data and writes the 6 CSV files read by load_data (src/data.py)."""
    tickers = [t for sector_tickers in UNIVERSE.values() for t in sector_tickers]
    tr, close = download_prices(tickers + [BENCHMARK], START)
    bench, tr, close = tr[BENCHMARK], tr.drop(columns=BENCHMARK), close.drop(columns=BENCHMARK)
    book, roe = {}, {}
    for ticker in tickers:
        try:
            accounts = download_accounts(ticker)
        except Exception as error:  # one failing stock must not block the 49 others
            print(f"{ticker}: accounts unavailable ({error})")
            continue
        book[ticker], roe[ticker] = accounts["book_per_share"], accounts["roe"]
    files = {
        "tr_index.csv": tr,
        "book_to_price.csv": to_month_ends(pd.DataFrame(book), tr.index) / close,
        "roe.csv": to_month_ends(pd.DataFrame(roe), tr.index),
        # current composition only: a stock counts as a member as soon as it trades
        "member.csv": tr.notna().astype(int),
        "bench.csv": pd.DataFrame({"bench": bench, "rf": RF_PCT}),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in files.items():
        table.rename_axis("date").to_csv(OUT_DIR / name)
    sectors = {t: sector for sector, sector_tickers in UNIVERSE.items() for t in sector_tickers}
    pd.Series(sectors, name="sector").rename_axis("ticker").to_csv(OUT_DIR / "sector.csv")
    print(f"6 files written to {OUT_DIR}/: {tr.index[0]:%m/%Y} to {tr.index[-1]:%m/%Y}")


if __name__ == "__main__":
    main()
