import streamlit as st
import pandas as pd
from models import Session, StrategyParam, Trade, Account
from data import fetch_historical_data
from strategy import MACrossoverStrategy

st.set_page_config(page_title="Auto Trade Dashboard", layout="wide")

st.title("自動売買シミュレーション＆トレード ダッシュボード")

session = Session()

# 0. Account Info
st.header("口座情報 (Account)")
account = session.query(Account).first()
if not account:
    account = Account(balance=1000000.0)
    session.add(account)
    session.commit()

col1, col2 = st.columns(2)
with col1:
    st.metric("現在の余力 (Balance)", f"¥{account.balance:,.0f}")
with col2:
    with st.expander("余力の設定 / 入金"):
        new_balance = st.number_input("余力を入力してください (円)", min_value=0, value=int(account.balance), step=10000)
        if st.button("更新する"):
            account.balance = new_balance
            session.commit()
            st.success(f"余力を {new_balance:,}円 に更新しました！")
            st.rerun()

st.divider()

# 1. Read strategy parameters
params = session.query(StrategyParam).all()

if not params:
    st.warning("最適化されたパラメータが見つかりません。先に `python simulation.py` を実行して学習させてください。")
else:
    st.subheader("学習済み 最適パラメータ")
    param_data = []
    for p in params:
        param_data.append({
            "銘柄 (Ticker)": p.ticker,
            "短期移動平均 (Short MA)": p.short_window,
            "長期移動平均 (Long MA)": p.long_window,
            "最終更新": p.updated_at
        })
    st.table(pd.DataFrame(param_data))

    # 2. View specific ticker data
    selected_ticker = st.selectbox("銘柄を選択", [p.ticker for p in params])

    if selected_ticker:
        # Fetch the selected param
        param = session.query(StrategyParam).filter_by(ticker=selected_ticker).first()

        st.subheader(f"{selected_ticker} の最新チャートと売買シグナル")

        # Fetch recent data
        history_days = f"{param.long_window + 30}d"
        # Since we changed how trading.py maps yfinance periods, let's use a safe static period for dashboard visualization
        df = fetch_historical_data(selected_ticker, period="1y")

        if not df.empty:
            # Apply strategy to get MAs and Signals
            strategy = MACrossoverStrategy(param.short_window, param.long_window)
            df_signals = strategy.generate_signals(df)

            # Prepare chart data
            chart_data = df_signals[['Close', 'SMA_short', 'SMA_long']].tail(100) # last 100 days

            # Display Line Chart
            st.line_chart(chart_data)

            # Show recent signals
            st.subheader("直近の売買シグナル (直近10日)")
            recent_signals = df_signals[['Close', 'SMA_short', 'SMA_long', 'Signal', 'Position']].tail(10)

            def map_action(pos):
                if pos in [1, 2]: return "BUY"
                elif pos in [-1, -2]: return "SELL"
                return "HOLD"

            recent_signals['Action'] = recent_signals['Position'].apply(map_action)
            st.dataframe(recent_signals)

# 3. Read Trade History
st.subheader("実際のトレード履歴 (trading.py 実行結果)")
trades = session.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
if not trades:
    st.info("トレード履歴がありません。")
else:
    trade_data = []
    for t in trades:
        trade_data.append({
            "日時": t.timestamp,
            "銘柄": t.ticker,
            "アクション": t.action,
            "株数": t.shares,
            "価格": f"¥{t.price:,.2f}",
            "損益 (PnL)": f"¥{t.pnl:,.2f}" if t.pnl is not None else "-"
        })
    st.dataframe(pd.DataFrame(trade_data))

session.close()
