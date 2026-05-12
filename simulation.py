import itertools
from data import fetch_historical_data
from strategy import MACrossoverStrategy
from models import Session, StrategyParam, Account, init_db

def run_simulation(ticker: str):
    print(f"Starting simulation for {ticker}...")
    df = fetch_historical_data(ticker, period='1y')
    if df.empty:
        print("Cannot simulate without data.")
        return

    initial_capital = 1000000.0
    best_pnl = initial_capital
    best_params = (None, None)

    short_windows = [5, 10, 15, 20]
    long_windows = [20, 30, 50, 100]

    # Fixed parameters for strict rules
    min_volume = 1000000
    price_change_pct = 0.01
    take_profit_pct = 0.10
    stop_loss_pct = 0.05

    for short, long in itertools.product(short_windows, long_windows):
        if short >= long:
            continue

        strategy = MACrossoverStrategy(short, long, min_volume, price_change_pct, take_profit_pct, stop_loss_pct)
        final_capital = strategy.backtest(df, initial_capital)

        profit = final_capital - initial_capital
        print(f"Tested short={short}, long={long} -> PnL: {profit:.2f}")

        if final_capital > best_pnl:
            best_pnl = final_capital
            best_params = (short, long)

    if best_params[0] is not None:
        print(f"Best parameters found: short={best_params[0]}, long={best_params[1]} with PnL: {best_pnl - initial_capital:.2f}")

        # Save to database
        session = Session()

        # Initialize Account if it doesn't exist
        account = session.query(Account).first()
        if not account:
            account = Account(balance=initial_capital)
            session.add(account)

        param = session.query(StrategyParam).filter_by(ticker=ticker).first()
        if not param:
            param = StrategyParam(ticker=ticker)
            session.add(param)

        param.short_window = best_params[0]
        param.long_window = best_params[1]
        param.min_volume = min_volume
        param.price_change_pct = price_change_pct
        param.take_profit_pct = take_profit_pct
        param.stop_loss_pct = stop_loss_pct
        session.commit()
        session.close()
        print("Saved best parameters to database.")
    else:
        print("No profitable parameters found. Will not update database.")

import json
import os

if __name__ == "__main__":
    init_db()

    # リサーチAI (screener.py) が生成したポートフォリオを読み込む
    portfolio_file = "portfolio.json"
    if os.path.exists(portfolio_file):
        with open(portfolio_file, "r") as f:
            portfolio = json.load(f)
        print(f"🤖 [運用AI] リサーチAIから {len(portfolio)} 銘柄のリストを受信しました。")
    else:
        print("⚠️ portfolio.json が見つかりません。デフォルトのポートフォリオを使用します。")
        portfolio = ["7203.T", "6758.T", "8306.T", "8058.T", "9433.T"]

    print("=== ポートフォリオ一括シミュレーション＆最適化 ===")
    for ticker in portfolio:
        run_simulation(ticker)
        print("-" * 40)
