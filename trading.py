from data import fetch_latest_data, fetch_historical_data
from strategy import MACrossoverStrategy
from models import Session, StrategyParam, Trade, init_db

def run_trading(ticker: str):
    print(f"Starting actual trading logic for {ticker}...")

    # 1. Fetch optimal parameters from DB
    session = Session()
    param = session.query(StrategyParam).filter_by(ticker=ticker).first()
    if not param:
        print(f"No optimized parameters found for {ticker}. Run simulation first.")
        session.close()
        return

    print(f"Loaded optimal parameters from DB: short_window={param.short_window}, long_window={param.long_window}")

    # 2. Fetch data
    # For actual trading with moving averages we need enough history for the long window
    # Map long window into standard yfinance period strings
    required_days = param.long_window + 10
    if required_days <= 5:
        period = "5d"
    elif required_days <= 30:
        period = "1mo"
    elif required_days <= 90:
        period = "3mo"
    elif required_days <= 180:
        period = "6mo"
    elif required_days <= 365:
        period = "1y"
    elif required_days <= 730:
        period = "2y"
    else:
        period = "5y"

    df = fetch_historical_data(ticker, period=period)
    if df.empty:
        print("Cannot fetch data for trading.")
        session.close()
        return

    # 3. Apply Strategy
    strategy = MACrossoverStrategy(short_window=param.short_window, long_window=param.long_window)
    df_signals = strategy.generate_signals(df)

    latest_data = df_signals.iloc[-1]
    signal = latest_data['Signal']
    price = latest_data['Close']

    action = None
    if latest_data['Position'] in [1, 2]:
        action = "BUY"
    elif latest_data['Position'] in [-1, -2]:
        action = "SELL"
    else:
        action = "HOLD"

    print(f"Latest Price: {price:.2f}")
    print(f"Action: {action}")

    # 4. If BUY/SELL, record to DB (simulated actual trade)
    if action in ["BUY", "SELL"]:
        # Simulate trading 100 shares
        shares = 100
        new_trade = Trade(
            ticker=ticker,
            action=action,
            price=price,
            shares=shares
        )
        session.add(new_trade)
        session.commit()
        print(f"Recorded trade in DB: {action} {shares} shares at {price:.2f}")

    session.close()

if __name__ == "__main__":
    init_db()
    run_trading("7203.T")
