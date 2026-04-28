import pandas as pd

class MACrossoverStrategy:
    def __init__(self, short_window: int = 10, long_window: int = 30):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates buy/sell signals based on moving average crossover.
        1 = Buy
        -1 = Sell
        0 = Hold
        """
        if len(df) < self.long_window:
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
        df['Position'] = df['Signal'].diff()

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

        for index, row in df.iterrows():
            if pd.isna(row['Position']):
                continue

            # Buy signal
            if row['Position'] == 1 or row['Position'] == 2:
                if capital > 0:
                    shares_to_buy = int(capital // row['Close'])
                    if shares_to_buy > 0:
                        position += shares_to_buy
                        capital -= shares_to_buy * row['Close']
            # Sell signal
            elif row['Position'] == -1 or row['Position'] == -2:
                if position > 0:
                    capital += position * row['Close']
                    position = 0

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
