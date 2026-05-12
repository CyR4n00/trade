import yfinance as yf
import pandas as pd
import json
import os

try:
    from google import genai
except ImportError:
    genai = None

# 日本の主要企業群（TOPIX Core30などから抜粋した監視対象ユニバース）
# 今後、外部API等から動的に取得することも可能
UNIVERSE = [
    "7203.T", # トヨタ自動車
    "6758.T", # ソニーグループ
    "8306.T", # 三菱UFJ
    "8058.T", # 三菱商事
    "9433.T", # KDDI
    "9984.T", # ソフトバンクグループ
    "6861.T", # キーエンス
    "8035.T", # 東京エレクトロン
    "6098.T", # リクルートHD
    "7974.T", # 任天堂
    "4063.T", # 信越化学工業
    "4502.T", # 武田薬品工業
    "6501.T", # 日立製作所
    "8001.T", # 伊藤忠商事
    "6981.T", # 村田製作所
    "7267.T", # 本田技研工業
    "9432.T", # NTT
    "8316.T", # 三井住友FG
    "8031.T", # 三井物産
    "6902.T"  # デンソー
]

def analyze_and_screen(tickers: list, top_n: int = 5) -> list:
    """
    リサーチAIモジュール:
    指定された銘柄群から、直近1ヶ月のモメンタム（価格上昇率）と出来高を基に
    最も期待値の高い銘柄を抽出し、ポートフォリオとして返す。
    """
    print("🤖 [リサーチAI] 市場全体のスクリーニングを開始します...")

    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # 過去1ヶ月のデータを取得
            hist = stock.history(period="1mo")
            if hist.empty or len(hist) < 20:
                continue

            start_price = hist['Close'].iloc[0]
            end_price = hist['Close'].iloc[-1]
            avg_volume = hist['Volume'].mean()

            # モメンタム（1ヶ月間の上昇率）を計算
            momentum = (end_price - start_price) / start_price

            results.append({
                "ticker": ticker,
                "momentum": momentum,
                "avg_volume": avg_volume
            })
        except Exception as e:
            print(f"⚠️ {ticker} のデータ取得に失敗しました: {e}")

    df = pd.DataFrame(results)

    if df.empty:
        print("⚠️ [リサーチAI] 有効なデータが見つかりませんでした。")
        return tickers[:top_n]

    # フィルタリング: 流動性が確保されている（平均出来高 100万株以上）
    df = df[df['avg_volume'] >= 1000000]

    # スコアリング: モメンタムが高い順にソート
    df = df.sort_values(by="momentum", ascending=False)

    # 上位N銘柄を選出
    top_picks = df.head(top_n)['ticker'].tolist()

    print(f"✅ [リサーチAI] 一次スクリーニング完了。上位 {len(top_picks)} 銘柄を選定しました。")

    # Gemini API連携によるセンチメント分析 (LLM連携)
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and genai:
        print("🤖 [リサーチAI] Gemini APIを使用して、選定された銘柄の最新の市場センチメントを分析します...")
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"以下の日本株のティッカーシンボルについて、今日の投資家センチメントや関連する最新のポジティブ・ネガティブな要因をそれぞれ1行で簡潔に分析してください。\n対象銘柄: {', '.join(top_picks)}"
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            print("📝 【Gemini 市場分析レポート】")
            print(response.text)
        except Exception as e:
            print(f"⚠️ Gemini APIの呼び出しに失敗しました: {e}")
    else:
        print("💡 Gemini APIキーが設定されていないため、LLMによる定性的なセンチメント分析はスキップされました。")

    for pick in top_picks:
        row = df[df['ticker'] == pick].iloc[0]
        print(f"   - {pick} (1ヶ月モメンタム: {row['momentum']*100:.2f}%, 平均出来高: {row['avg_volume']:,.0f}株)")

    return top_picks

if __name__ == "__main__":
    selected_portfolio = analyze_and_screen(UNIVERSE, top_n=5)

    # 運用AI（simulation.py）と 執行AI（trading.py）に渡すためにファイルに保存
    with open("portfolio.json", "w") as f:
        json.dump(selected_portfolio, f)

    print("📁 [連携] portfolio.json に選定結果を保存しました。")
