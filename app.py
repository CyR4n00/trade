import streamlit as st
import pandas as pd
from models import Session, StrategyParam, Trade, Account, AnalysisReport, init_db
from data import fetch_historical_data
from strategy import MACrossoverStrategy

# Initialize DB to prevent crashes if it was manually deleted
init_db()

st.set_page_config(page_title="Auto Trade Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- Sidebar (Settings & Mobile Menu) ---
with st.sidebar:
    st.title("⚙️ アプリ設定")
    st.markdown("他のユーザーも利用できるSaaS型AIトレードアプリの設定画面です。")

    st.subheader("🤖 AI連携設定")
    # Store API key in session state
    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = ""

    api_key_input = st.text_input("Gemini API キー", value=st.session_state["gemini_api_key"], type="password", help="ここにAPIキーを入力すると、次回の高度なAI分析（リサーチ・反省）に利用されます。")
    if api_key_input != st.session_state["gemini_api_key"]:
        st.session_state["gemini_api_key"] = api_key_input
        st.success("APIキーを保存しました！(セッション中のみ有効)")

    st.divider()

    st.subheader("🚀 システム実行 (手動コントローラー)")
    st.markdown("ボタンを押すことで、各AIエージェントを直接起動します。")

    import subprocess
    import sys
    import os

    # Windows環境の文字化け対策: 子プロセスにUTF-8を強制する
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # Gemini APIキーをバックエンドのスクリプトに渡す
    if st.session_state.get("gemini_api_key"):
        env["GEMINI_API_KEY"] = st.session_state["gemini_api_key"]

    if st.button("① リサーチAIを実行 (銘柄選定)", use_container_width=True):
        with st.spinner("市場をスクリーニング中..."):
            result = subprocess.run([sys.executable, "screener.py"], capture_output=True, text=True, encoding="utf-8", env=env)
            if result.returncode == 0:
                st.success("リサーチ完了！")
                st.code(result.stdout)
            else:
                st.error("エラーが発生しました。")
                st.code(result.stderr)

    if st.button("② 運用AIを実行 (最適化)", use_container_width=True):
        with st.spinner("シミュレーション＆パラメータ最適化中... (数分かかります)"):
            result = subprocess.run([sys.executable, "simulation.py"], capture_output=True, text=True, encoding="utf-8", env=env)
            if result.returncode == 0:
                st.success("最適化完了！")
                st.code(result.stdout[-500:]) # Show last part to save space
            else:
                st.error("エラーが発生しました。")
                st.code(result.stderr)

    if st.button("③ 執行AIを実行 (トレード判定)", type="primary", use_container_width=True):
        with st.spinner("取引判定＆実行中..."):
            result = subprocess.run([sys.executable, "trading.py"], capture_output=True, text=True, encoding="utf-8", env=env)
            if result.returncode == 0:
                st.success("本日の取引執行が完了しました！")
                st.code(result.stdout)
                # Force reload to show new trades and balances
                st.rerun()
            else:
                st.error("エラーが発生しました。")
                st.code(result.stderr)

    st.info("💡 定期的な自動実行（cron等）も可能ですが、スマホからこのボタンを押すことでも手動でAIを動かせます。")

# --- Main App ---
st.title("📈 自動売買AI ダッシュボード")

session = Session()

# 0. Account Info
st.header("💳 口座情報 (Account)")
account = session.query(Account).first()
if not account:
    account = Account(balance=1000000.0)
    session.add(account)
    session.commit()

st.metric("現在の現物買付余力 (Balance)", f"¥{account.balance:,.0f}")

with st.expander("余力の設定 / 入金（シミュレーション用）"):
    new_balance = st.number_input("余力を入力してください (円)", min_value=0, value=int(account.balance), step=10000)
    if st.button("更新する"):
        account.balance = new_balance
        session.commit()
        st.success(f"余力を {new_balance:,}円 に更新しました！")
        st.rerun()

st.divider()

# 0.5 Holdings Summary
st.header("💼 保有株式サマリー (Holdings)")

# Calculate current holdings from trades
trades = session.query(Trade).order_by(Trade.timestamp.asc()).all()
holdings = {}

for t in trades:
    if t.ticker not in holdings:
        holdings[t.ticker] = {"shares": 0, "total_cost": 0.0}

    if t.action == "BUY":
        holdings[t.ticker]["shares"] += t.shares
        holdings[t.ticker]["total_cost"] += (t.price * t.shares)
    elif t.action == "SELL":
        # Simplified: Assuming we sell all shares. Reset holdings.
        holdings[t.ticker]["shares"] = 0
        holdings[t.ticker]["total_cost"] = 0.0

summary_data = []
total_unrealized_pnl = 0.0
total_market_value = 0.0

for ticker, data in holdings.items():
    if data["shares"] > 0:
        avg_price = data["total_cost"] / data["shares"]

        # Fetch latest price to calculate unrealized PnL
        try:
            import yfinance as yf
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period="5d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
            else:
                current_price = avg_price # Fallback
        except:
            current_price = avg_price

        market_value = current_price * data["shares"]
        unrealized_pnl = market_value - data["total_cost"]

        total_market_value += market_value
        total_unrealized_pnl += unrealized_pnl

        summary_data.append({
            "銘柄": ticker,
            "保有株数": data["shares"],
            "取得単価": f"¥{avg_price:,.2f}",
            "現在値": f"¥{current_price:,.2f}",
            "評価額": f"¥{market_value:,.0f}",
            "評価損益": f"¥{unrealized_pnl:,.0f}"
        })

if not summary_data:
    st.info("現在保有している株式はありません。")
else:
    # Summary Metrics
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("株式評価額 計", f"¥{total_market_value:,.0f}")
    with col_b:
        st.metric("評価損益 計", f"¥{total_unrealized_pnl:,.0f}", delta=float(total_unrealized_pnl))

    st.markdown("### 保有銘柄一覧")
    for data in summary_data:
        with st.container(border=True):
            cols = st.columns([2, 1, 1])
            with cols[0]:
                st.markdown(f"**{data['銘柄']}**")
                st.markdown(f"{data['保有株数']:,}株 保有 (平均取得単価: {data['取得単価']})")
            with cols[1]:
                st.markdown("現在値")
                st.markdown(f"**{data['現在値']}**")
            with cols[2]:
                st.metric("評価損益", data['評価損益'], delta=float(data['評価損益'].replace('¥', '').replace(',', '')))

st.divider()

# 1. Read strategy parameters
params = session.query(StrategyParam).all()

if not params:
    st.warning("最適化されたパラメータが見つかりません。リサーチAIと運用AIを実行してください。")
else:
    st.header("📊 AI 学習済み 最適パラメータ")
    param_data = []
    for p in params:
        param_data.append({
            "銘柄 (Ticker)": p.ticker,
            "短期移動平均 (Short MA)": p.short_window,
            "長期移動平均 (Long MA)": p.long_window,
            "最終更新": p.updated_at
        })
    st.table(pd.DataFrame(param_data))

    # 2. View specific ticker data (Mobile friendly layout)
    st.subheader("チャートと売買シグナルの確認")
    selected_ticker = st.selectbox("銘柄を選択してください", [p.ticker for p in params])

    if selected_ticker:
        # Fetch the selected param
        param = session.query(StrategyParam).filter_by(ticker=selected_ticker).first()

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

            with st.expander("直近10日の詳細データとシグナルを見る"):
                recent_signals = df_signals[['Close', 'SMA_short', 'SMA_long', 'Signal', 'Position']].tail(10)

                def map_action(pos):
                    if pos in [1, 2]: return "BUY"
                    elif pos in [-1, -2]: return "SELL"
                    return "HOLD"

                recent_signals['Action'] = recent_signals['Position'].apply(map_action)
                st.dataframe(recent_signals, use_container_width=True)

# 3. Read Trade History
st.divider()
st.header("📝 AI 執行トレード履歴")
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
    st.dataframe(pd.DataFrame(trade_data), use_container_width=True)

# 4. View AI Analysis Report
st.divider()
st.header("🧠 AI トレード分析レポート (自己学習フィードバック)")
st.markdown("取引執行後に、AIが自身のトレードを振り返って作成したレポートです。")
reports = session.query(AnalysisReport).order_by(AnalysisReport.timestamp.desc()).limit(10).all()

if not reports:
    st.info("まだ分析レポートはありません。（売却取引が行われると生成されます）")
else:
    for rep in reports:
        with st.expander(f"{rep.timestamp.strftime('%Y-%m-%d %H:%M')} - {rep.ticker} ({rep.summary})"):
            st.write(f"**【良かった点】**\n{rep.good_points}")
            st.write(f"**【悪かった点・改善点】**\n{rep.bad_points}")

session.close()
