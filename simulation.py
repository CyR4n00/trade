import itertools
from data import fetch_historical_data
from strategy import MACrossoverStrategy
from models import Session, StrategyParam, init_db

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

    for short, long in itertools.product(short_windows, long_windows):
        if short >= long:
            continue

        strategy = MACrossoverStrategy(short, long)
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
        param = session.query(StrategyParam).filter_by(ticker=ticker).first()
        if not param:
            param = StrategyParam(ticker=ticker)
            session.add(param)

        param.short_window = best_params[0]
        param.long_window = best_params[1]
        session.commit()
        session.close()
        print("Saved best parameters to database.")
    else:
        print("No profitable parameters found. Will not update database.")

if __name__ == "__main__":
    init_db()
    run_simulation("7203.T")
