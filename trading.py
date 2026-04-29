from data import fetch_latest_data, fetch_historical_data
from strategy import MACrossoverStrategy
from models import Session, StrategyParam, Trade, Account, init_db

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

    # 4. If BUY/SELL, record to DB (simulated actual trade) and update Account balance
    if action in ["BUY", "SELL"]:
        shares = 100
        cost = price * shares

        # Ensure account exists
        account = session.query(Account).first()
        if not account:
            account = Account(balance=1000000.0)
            session.add(account)
            session.commit()

        pnl = None

        if action == "BUY":
            if account.balance >= cost:
                account.balance -= cost
                print(f"✅ 【フィードバック】 {shares}株を {price:.2f}円 で買付しました。（約定代金: {cost:.2f}円）")
                print(f"   現在の余力: {account.balance:.2f}円")
            else:
                print(f"❌ 【フィードバック】 {shares}株（{cost:.2f}円）を買付する余力（{account.balance:.2f}円）が足りません。見送ります。")
                action = None # Prevent recording trade
        elif action == "SELL":
            # Simple assumption: sell what we last bought.
            # In a real app we'd track specific open positions.
            last_buy = session.query(Trade).filter_by(ticker=ticker, action="BUY").order_by(Trade.timestamp.desc()).first()
            if last_buy:
                pnl = (price - last_buy.price) * shares
                account.balance += cost
                print(f"✅ 【フィードバック】 {shares}株を {price:.2f}円 で売却しました。（売却代金: {cost:.2f}円）")
                if pnl >= 0:
                    print(f"   🎉 利益確定: +{pnl:.2f}円")
                else:
                    print(f"   😢 損失確定: {pnl:.2f}円")
                print(f"   現在の余力: {account.balance:.2f}円")
            else:
                print("❌ 【フィードバック】 保有ポジションがないため、売却を見送ります。")
                action = None

        if action:
            new_trade = Trade(
                ticker=ticker,
                action=action,
                price=price,
                shares=shares,
                pnl=pnl
            )
            session.add(new_trade)
            session.commit()

    session.close()

if __name__ == "__main__":
    init_db()
    run_trading("7203.T")
