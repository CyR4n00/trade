import yfinance as yf
import pandas as pd

def fetch_historical_data(ticker_symbol: str, period: str = '2y') -> pd.DataFrame:
    """
    Fetch historical data for backtesting.
    Example ticker: '7203.T' for Toyota on TSE.
    """
    print(f"Fetching historical data for {ticker_symbol} over {period}...")
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period=period)
    if df.empty:
        print(f"Warning: No data found for {ticker_symbol}")
    return df

def fetch_latest_data(ticker_symbol: str) -> pd.DataFrame:
    """
    Fetch the latest available data for actual trading.
    """
    print(f"Fetching latest data for {ticker_symbol}...")
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period='5d') # fetch recent days just in case
    return df

if __name__ == "__main__":
    test_ticker = "7203.T"
    df = fetch_historical_data(test_ticker, period='1mo')
    print(f"Data rows: {len(df)}")
    print(df.tail())
