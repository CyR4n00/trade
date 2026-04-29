from data import fetch_latest_data, fetch_historical_data
from strategy import MACrossoverStrategy
from models import Session, StrategyParam, Trade, Account, AnalysisReport, init_db

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
        # Ensure account exists
        account = session.query(Account).first()
        if not account:
            account = Account(balance=1000000.0)
            session.add(account)
            session.commit()

        pnl = None

        if action == "BUY":
            # 日本株の単元株数(100株)をベースに、余力で買える最大株数を計算
            max_lots = int(account.balance // (price * 100))
            if max_lots > 0:
                shares = max_lots * 100
                cost = price * shares
                account.balance -= cost
                print(f"✅ 【フィードバック】 余力を活用し、{shares}株を {price:.2f}円 で買付しました。（約定代金: {cost:,.2f}円）")
                print(f"   現在の余力: {account.balance:,.2f}円")

                new_trade = Trade(ticker=ticker, action=action, price=price, shares=shares, pnl=None)
                session.add(new_trade)
                session.commit()
            else:
                print(f"❌ 【フィードバック】 100株（約{price*100:,.2f}円）を買付する余力（{account.balance:,.2f}円）が足りません。見送ります。")

        elif action == "SELL":
            # 持っている全ポジションを売却するシンプルなロジック
            last_buy = session.query(Trade).filter_by(ticker=ticker, action="BUY").order_by(Trade.timestamp.desc()).first()
            if last_buy:
                shares = last_buy.shares
                cost = price * shares
                pnl = (price - last_buy.price) * shares
                account.balance += cost

                print(f"✅ 【フィードバック】 {shares}株を {price:.2f}円 で売却しました。（売却代金: {cost:,.2f}円）")

                good_pts = ""
                bad_pts = ""
                summary = ""

                if pnl > 0:
                    print(f"   🎉 利益確定: +{pnl:,.2f}円")
                    good_pts = f"トレンドに乗り、{pnl:,.0f}円の利益を確保できました。"
                    bad_pts = "特になし。ルール通りの良いトレードです。"
                    summary = "成功したトレンドフォロー取引"
                else:
                    print(f"   😢 損失確定: {pnl:,.2f}円")
                    good_pts = "ルールに従い、早期に損切り（撤退）を実行できた点。"
                    bad_pts = f"エントリー直後にトレンドが逆行し、{abs(pnl):,.0f}円の損失。相場環境のダマシに遭った可能性。"
                    summary = "ルール通りの撤退（ロスカット）"

                print(f"   現在の余力: {account.balance:,.2f}円")

                # トレードとレポートの保存
                new_trade = Trade(ticker=ticker, action=action, price=price, shares=shares, pnl=pnl)
                session.add(new_trade)
                session.commit() # commit to get trade ID

                report = AnalysisReport(
                    ticker=ticker,
                    trade_id=new_trade.id,
                    good_points=good_pts,
                    bad_points=bad_pts,
                    summary=summary
                )
                session.add(report)
                session.commit()

            else:
                print("❌ 【フィードバック】 保有ポジションがないため、売却を見送ります。")

    session.close()

if __name__ == "__main__":
    init_db()
    portfolio = ["7203.T", "6758.T", "8306.T", "8058.T", "9433.T"]

    print("=== ポートフォリオ一括トレード判定 ===")
    for ticker in portfolio:
        run_trading(ticker)
        print("-" * 40)
