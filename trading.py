from data import fetch_latest_data, fetch_historical_data
from strategy import MACrossoverStrategy
from models import Session, StrategyParam, Trade, Account, AnalysisReport, init_db
import broker

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
    strategy = MACrossoverStrategy(
        short_window=param.short_window,
        long_window=param.long_window,
        min_volume=param.min_volume,
        price_change_pct=param.price_change_pct,
        take_profit_pct=param.take_profit_pct,
        stop_loss_pct=param.stop_loss_pct
    )
    df_signals = strategy.generate_signals(df)

    latest_data = df_signals.iloc[-1]
    price = latest_data['Close']

    action = None

    # 3.5 Check Forced Stop Loss / Take Profit first
    last_buy = session.query(Trade).filter_by(ticker=ticker, action="BUY").order_by(Trade.timestamp.desc()).first()
    last_sell = session.query(Trade).filter_by(ticker=ticker, action="SELL").order_by(Trade.timestamp.desc()).first()

    # Simple check to see if we currently hold a position
    has_position = False
    if last_buy:
        if not last_sell or last_buy.timestamp > last_sell.timestamp:
            has_position = True

    if has_position:
        buy_price = last_buy.price
        profit_ratio = (price - buy_price) / buy_price

        if profit_ratio >= param.take_profit_pct:
            action = "SELL"
            print(f"🎯 【自動利確】 目標利益率（+{param.take_profit_pct*100:.1f}%）に到達しました。")
        elif profit_ratio <= -param.stop_loss_pct:
            action = "SELL"
            print(f"🚨 【自動損切】 許容損失率（-{param.stop_loss_pct*100:.1f}%）に到達しました。")

    # If no forced action, fallback to standard MA and filter signals
    if not action:
        if latest_data['Position'] in [1, 2]:
            action = "BUY"
        elif latest_data['Position'] in [-1, -2] and has_position:
            action = "SELL"
            print(f"📉 【サイン売却】 移動平均線のデッドクロスが発生しました。")
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

                # --- 証券API連携 (Mock) ---
                api_response = broker.execute_buy(ticker, shares, price)
                if api_response.get("status") == "success":
                    account.balance -= cost
                    print(f"✅ 【フィードバック】 余力を活用し、{shares}株を {price:.2f}円 で買付しました。（約定代金: {cost:,.2f}円）")
                    print(f"   現在の余力: {account.balance:,.2f}円")

                    new_trade = Trade(ticker=ticker, action=action, price=price, shares=shares, pnl=None)
                    session.add(new_trade)
                    session.commit()
                else:
                    print("❌ 【APIエラー】 買付注文の送信に失敗しました。")
            else:
                print(f"❌ 【フィードバック】 100株（約{price*100:,.2f}円）を買付する余力（{account.balance:,.2f}円）が足りません。見送ります。")

        elif action == "SELL":
            # 持っている全ポジションを売却するシンプルなロジック
            if has_position and last_buy:
                shares = last_buy.shares
                cost = price * shares
                pnl = (price - last_buy.price) * shares

                # --- 証券API連携 (Mock) ---
                api_response = broker.execute_sell(ticker, shares, price)
                if api_response.get("status") == "success":
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
                    print("❌ 【APIエラー】 売却注文の送信に失敗しました。")

            else:
                print("❌ 【フィードバック】 保有ポジションがないため、売却を見送ります。")

    session.close()

import json
import os

if __name__ == "__main__":
    init_db()

    # リサーチAI (screener.py) が生成したポートフォリオを読み込む
    portfolio_file = "portfolio.json"
    if os.path.exists(portfolio_file):
        with open(portfolio_file, "r") as f:
            portfolio = json.load(f)
        print(f"🤖 [執行AI] リサーチAIから指示された {len(portfolio)} 銘柄の取引予算と執行判定を開始します。")
    else:
        print("⚠️ portfolio.json が見つかりません。デフォルトのポートフォリオを使用します。")
        portfolio = ["7203.T", "6758.T", "8306.T", "8058.T", "9433.T"]

    print("=== ポートフォリオ一括トレード判定 ===")
    for ticker in portfolio:
        run_trading(ticker)
        print("-" * 40)
