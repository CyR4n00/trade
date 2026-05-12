import pandas as pd

class MACrossoverStrategy:
    def __init__(self, short_window: int = 10, long_window: int = 30,
                 min_volume: int = 1000000, price_change_pct: float = 0.01,
                 take_profit_pct: float = 0.10, stop_loss_pct: float = 0.05):
        self.short_window = short_window
        self.long_window = long_window
        self.min_volume = min_volume
        self.price_change_pct = price_change_pct
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates buy/sell signals based on moving average crossover.
        1 = Buy
        -1 = Sell
        0 = Hold
        """
        if len(df) < self.long_window:
            df = df.copy()
            df['Signal'] = 0
            df['Position'] = 0
            df['SMA_short'] = 0
            df['SMA_long'] = 0
            return df

        df = df.copy()
        df['SMA_short'] = df['Close'].rolling(window=self.short_window, min_periods=1).mean()
        df['SMA_long'] = df['Close'].rolling(window=self.long_window, min_periods=1).mean()

        df['Signal'] = 0
        # Buy when short MA crosses above long MA
        df.loc[df['SMA_short'] > df['SMA_long'], 'Signal'] = 1
        # Sell when short MA crosses below long MA
        df.loc[df['SMA_short'] < df['SMA_long'], 'Signal'] = -1

        # Calculate daily positions (changes in signal)
        if len(df) > 0:
            df['Position'] = df['Signal'].diff()

            # Filter 1 & 2: Only apply entry filters to new BUY triggers (Position == 1 or 2)
            # If the entry conditions are not met, we cancel the BUY trigger by setting Position = 0

            # Volume condition
            if 'Volume' in df.columns:
                df.loc[(df['Position'] > 0) & (df['Volume'] < self.min_volume), 'Position'] = 0

            # Price volatility condition
            df['Daily_Return'] = df['Close'].pct_change().abs()
            df.loc[(df['Position'] > 0) & (df['Daily_Return'] < self.price_change_pct), 'Position'] = 0

        else:
            df['Position'] = pd.Series(dtype=float)

        return df

    def backtest(self, df: pd.DataFrame, initial_capital: float = 1000000.0) -> float:
        """
        Simulate trading to calculate final PnL.
        """
        df = self.generate_signals(df)

        if 'Position' not in df.columns:
            return initial_capital

        capital = initial_capital
        position = 0 # Number of shares
        buy_price = 0.0

        for index, row in df.iterrows():
            # 1. Check Stop Loss / Take Profit first if we hold a position
            if position > 0:
                current_price = row['Close']
                profit_ratio = (current_price - buy_price) / buy_price

                # Take Profit
                if profit_ratio >= self.take_profit_pct:
                    capital += position * current_price
                    position = 0
                    buy_price = 0.0
                    continue # Skip normal MA signals today

                # Stop Loss
                if profit_ratio <= -self.stop_loss_pct:
                    capital += position * current_price
                    position = 0
                    buy_price = 0.0
                    continue # Skip normal MA signals today

            # 2. Check standard signals
            if pd.isna(row['Position']):
                continue

            # Buy signal
            if row['Position'] in [1, 2]:
                if capital > 0 and position == 0:
                    shares_to_buy = int(capital // row['Close'])
                    if shares_to_buy > 0:
                        position += shares_to_buy
                        capital -= shares_to_buy * row['Close']
                        buy_price = row['Close']
            # Sell signal
            elif row['Position'] in [-1, -2]:
                if position > 0:
                    capital += position * row['Close']
                    position = 0
                    buy_price = 0.0

        # Final value
        if position > 0:
            capital += position * df.iloc[-1]['Close']

        return capital

if __name__ == "__main__":
    import numpy as np
    # Quick test
    dates = pd.date_range("2026-01-01", periods=50)
    data = pd.DataFrame({
        "Close": np.linspace(100, 200, 50) # Uptrend
    }, index=dates)

    strategy = MACrossoverStrategy(5, 10)
    result = strategy.backtest(data, 10000)
    print(f"Final capital: {result}")
