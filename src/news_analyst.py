"""
ニュース分析モジュール
Gemini APIを使用して市場ニュースの要約・分析レポートを生成します。
"""
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Gemini APIの初期化
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def configure_gemini(api_key: Optional[str] = None) -> bool:
    """
    Gemini APIを設定します。
    
    Args:
        api_key: APIキー（省略時はStreamlit secrets/環境変数から取得）
    
    Returns:
        設定成功時True
    """
    if not GEMINI_AVAILABLE:
        return False
    
    # 1. 引数で渡された場合
    key = api_key
    
    # 2. Streamlit Cloud secrets から取得
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass
    
    # 3. 環境変数から取得
    if not key:
        key = os.getenv("GEMINI_API_KEY")
    
    if not key:
        return False
    
    genai.configure(api_key=key)
    return True


def generate_flash_summary(
    market_data: dict,
    news_headlines: list[str],
    option_summary: Optional[str] = None
) -> str:
    """
    Flash Summary（速報箇条書き）を生成します。
    
    Args:
        market_data: 市場指数データ
        news_headlines: ニュースヘッドライン
        option_summary: オプション分析の要約
    
    Returns:
        フォーマット済みのFlash Summary
    """
    lines = []
    
    # 指数
    if "S&P 500" in market_data:
        sp = market_data["S&P 500"]
        lines.append(f"■ S&P500 {sp['change']:+.2f}%")
    if "Nasdaq" in market_data:
        nq = market_data["Nasdaq"]
        lines.append(f"■ ナスダック {nq['change']:+.2f}%")
    
    # 金利
    treasury_line = []
    if "2Y Treasury" in market_data:
        treasury_line.append(f"2y {market_data['2Y Treasury']['price']:.3f}%")
    if "10Y Treasury" in market_data:
        treasury_line.append(f"10y {market_data['10Y Treasury']['price']:.3f}%")
    if "30Y Treasury" in market_data:
        treasury_line.append(f"30y {market_data['30Y Treasury']['price']:.3f}%")
    if treasury_line:
        lines.append(f"■ {', '.join(treasury_line)}")
    
    # 為替・商品
    fx_commodity = []
    if "USD/JPY" in market_data:
        fx_commodity.append(f"ドル円 {market_data['USD/JPY']['price']:.2f}")
    if "WTI Crude" in market_data:
        fx_commodity.append(f"WTI {market_data['WTI Crude']['change']:+.2f}%")
    if "Bitcoin" in market_data:
        fx_commodity.append(f"₿ {market_data['Bitcoin']['change']:+.2f}%")
    if "Gold" in market_data:
        fx_commodity.append(f"金 {market_data['Gold']['change']:+.2f}%")
    if "Silver" in market_data:
        fx_commodity.append(f"銀 {market_data['Silver']['change']:+.2f}%")
    if "Copper" in market_data:
        fx_commodity.append(f"銅 {market_data['Copper']['change']:+.2f}%")
    if fx_commodity:
        lines.append(f"■ {', '.join(fx_commodity)}")
    
    # ニュースヘッドライン
    for headline in news_headlines[:8]:
        lines.append(f"■ {headline}")
    
    return "\n".join(lines)


def generate_market_recap(
    market_data: dict,
    news_data: list[dict],
    option_analysis: list[dict],
    theme_analysis: Optional[str] = None
) -> str:
    """
    Gemini APIを使用してMarket Recap（ナラティブ解説）を生成します。
    
    Args:
        market_data: 市場指数データ
        news_data: ニュース記事データ
        option_analysis: オプション分析結果
    
    Returns:
        ナラティブ形式の市況解説
    """
    if not GEMINI_AVAILABLE:
        return "Gemini APIが利用できません。APIキーを設定してください。"
    
    # コンテキストの構築
    context_parts = []
    
    # 市場データ（5日変動）
    context_parts.append("【短期変動 (5日)】")
    for name, data in market_data.items():
        if name not in ("trend_1mo", "weekly_performance"):
            context_parts.append(f"- {name}: {data.get('price', 'N/A')}, 変化: {data.get('change', 0):+.2f}%")
    
    # 週次パフォーマンス（アセットクラス横断）
    if "weekly_performance" in market_data:
        context_parts.append("\n【週次パフォーマンス (1週間) - アセットクラス横断】")
        for name, change in market_data["weekly_performance"].items():
            context_parts.append(f"- {name}: {change}")
            
    # 中期トレンド (1ヶ月)
    if "trend_1mo" in market_data:
        context_parts.append("\n【中期トレンド (1ヶ月)】")
        for name, data in market_data["trend_1mo"].items():
            context_parts.append(f"- {name}: {data['trend']} ({data['change_1mo']})期間: {data['start_date']}~{data['end_date']}")

    # ニュース（件数拡大、カテゴリ表示）
    context_parts.append("\n【ニュースヘッドライン (AI・テック・市場・マクロ・コモディティ・暗号資産)】")
    for news in news_data[:60]:  # 60件に拡大
        related = f"[{news.get('related_ticker', '')}] " if news.get('related_ticker') else ""
        category = f"({news.get('category', '')})" if news.get('category') else ""
        source = f"[{news.get('source', '')}]" if news.get('source') else ""
        title = news.get("title", "")
        summary = news.get("summary", "")
        if summary:
            context_parts.append(f"- {source}{related}{title} {category}\n  (Summary: {summary[:200]})")
        else:
            context_parts.append(f"- {source}{related}{title} {category}")
    
    # オプション分析
    if option_analysis:
        context_parts.append("\n【オプション市場構造】")
        for opt in option_analysis:
            ticker = opt.get("ticker", "")
            sentiment = opt.get("sentiment", "")
            analysis = opt.get("analysis", [])
            context_parts.append(f"- {ticker}: {sentiment}")
            for a in analysis:
                context_parts.append(f"  - {a}")

    # テーマ別トレンド
    if theme_analysis:
        context_parts.append(f"\n{theme_analysis}")
    
    # ユーザー参照知識
    try:
        from src.knowledge_storage import get_knowledge_for_ai_context
        knowledge_context = get_knowledge_for_ai_context(max_items=10)
        if knowledge_context:
            context_parts.append(f"\n{knowledge_context}")
    except Exception as e:
        print(f"Knowledge context error: {e}")
    
    context = "\n".join(context_parts)
    
    # 決算データの取得と追加
    earnings_section = ""
    try:
        from src.earnings_data import get_earnings_context_for_recap
        earnings_context = get_earnings_context_for_recap()
        if earnings_context:
            context += f"\n\n{earnings_context}"
            earnings_section = """
### Ⅴ. 主要決算サマリー (Earnings Highlights)
Context: 直近発表された主要企業の決算結果。
- EPS Beat/Miss、サプライズ率を分析
- ガイダンスの強弱と市場反応
- セクター別の決算トレンド
- 決算を受けた株価反応と今後の見通し

*(決算データがない場合、このセクションは省略)*
"""
    except Exception as e:
        print(f"Earnings context error: {e}")
    


    prompt = f"""# SYSTEM ROLE & OBJECTIVE
You are the "Macro Quant Analyst" at a top-tier Global Macro Hedge Fund.
Your client: Institutional investors (Sovereign Wealth Funds, Pension Funds).
Your Goal: Generate a "Market Analysis Report" that provides genuine "Alpha" (insight), not just a summary.
Synthesize fragmented information into a coherent "Narrative" with deep structural insights.

# COGNITIVE FRAMEWORK (Chain of Thought - Execute Implicitly)
1. **Filter Noise**: Discard generic news. Identify "Key Events" that trigger trend shifts.
2. **Second-Order Effects**: "If A happens → B is affected → C moves" (e.g., Oil↑ → Inflation expectations↑ → Yields↑ → Growth stocks↓).
3. **Reaction Function**: Focus on HOW the market *reacts*, not just the data. (Bad news + Stocks↑ = Liquidity play?)
4. **Flow Analysis**: Infer "Smart Money" positioning vs. "Retail" sentiment from price action and options.
5. **Confluence Check**: Do Technicals support Fundamentals? Identify divergences.

# CROSS-ASSET LINKAGE FRAMEWORK (CRITICAL - Apply Throughout)
Do NOT analyze each asset class in isolation. Identify and explain these linkages:
1. **Risk-On/Off Signals**: VIX↑ + Gold↑ + JPY↑ = Risk-Off. Track divergences.
2. **Liquidity Proxy**: BTC and small-caps (IWM) correlation as liquidity barometer.
3. **Curve Dynamics**: Yield curve shape changes → Equity valuation implications.
4. **Commodity-Equity Nexus**: Copper/Oil movements → Cyclical sector outlook.
5. **FX-Equity Correlation**: Dollar strength/weakness → MNC earnings impact.
6. **Crypto-Equity Linkage**: De-leveraging in crypto → Potential sell-off contagion.

# STYLE GUIDELINES (STRICT)
- **Role**: Act as a cold, calculating Macro Quant.
- **Language**: JAPANESE only.
- **Tone**: **Professional, Cold, High-Density**. NO "です・ます". USE "だ・である" or 体言止め.
  * Bad: 金利が上昇しました。様子見が必要です。
  * Good: 金利急騰。ベア・スティープニング鮮明化。警戒水準。
- **No Fluff**: Remove ALL filler words, hedges, and generic advice ("注意が必要", "期待される", "今後の動向に注目").
- **Jargon Density**: High. (Gamma, VIX Term Structure, CTAs, RRP, Term Premium, Breakeven, Short cover, Washout, etc.)
- **Narrative**: Connect dots logically. Weave a story, don't just list bullets.
- **Escape $ signs** for LaTeX compatibility.

# INPUT DATA
{context}

# OUTPUT FORMAT (MARKDOWN) - 3 SECTIONS ONLY

## [タイトル: 現在のマーケットレジームを端的に表すキャッチフレーズ (例: Risk-On / Disinflationary Growth / Stagflation Fear)]

### Ⅰ. 市場アップデート (本日の日付)

**統合ナラティブ形式で以下の要素を織り込む（箇条書きではなくストーリーとして記述）:**

**A. 主要指数・資産クラス動向**
- 市場の「レジーム（局面）」を定義。
- 表面的な価格変化ではなく、市場の「内部構造」と「質」を評価。
- 株価指数、国債、クレジット、FX、コモディティ、暗号資産（リスク資産の極北としての動向）。

**B. 時間軸別分析**
- **Short (Days)**: ボラティリティ、直近のホットテーマ、日次モメンタム。
- **Medium (1 Mo)**: トレンド強度、押し目買い圧力、テーマ遷移。
- **Long (YTD)**: 主要トレンドラインからの乖離、マクロ・政策トレンド累積。

**C. マクロ・政策コンテキスト**
- 金利動向が他アセットに与える影響。
- SOFRカーブ、マクロ指標に基づくカーブの変化、実質金利、インフレ期待。
- インフレダイナミクスとGeopoliticsの市場インパクト。

**D. センチメント・ポジショニング**
- オプション構造：VIX単体ではなく、VXターム構造（コンタンゴ/バックワーデーション）やSkewからの示唆。
- 需給歪みリスク（0DTE、強制需要、ウォッシュアウト）。
- Extreme Positioning判定 (Euphoria vs Capitulation) と Smart Money vs Retail の乖離。

**E. テクニカル・ブレッス**
- 内部構造の評価：ブレッドス、参加率、マクレランオシレーター。
- 主要移動平均（20EMA/50SMA/200SMA）との乖離とサポート/レジスタンス。
- Momentum (RSI/MACD) とセクター間スプレッド。

*(Dense, assertive narrative paragraph - integrate A through E into a cohesive story)*

---

### Ⅱ. 資金循環と投資テーマ (Themes & Flows)

**アセットクラス横断で資金フローとテーマ動態を分析:**

1. **Cross-Asset Flows**: 株式⇔債券⇔コモディティ⇔暗号資産間の資金移動
2. **Theme Lifecycle**: 各テーマの成熟度（黎明期/加速期/過熟期/衰退期）
3. **Rotation Dynamics**: セクター間・スタイル間（Growth↔Value, Large↔Small）の資金移動
4. **Smart Money vs Retail**: 機関投資家のポジショニング vs 個人のセンチメント乖離
5. **Narrative Shifts**: 支配的ナラティブの変化（「週次〜月次のストーリー」として記述）
6. **Crowding Risk**: 過度に集中したポジション（Magnificent 7偏重等）のリスク評価

| テーマ | ステータス | 資金フロー | 備考 |
|:---|:---|:---|:---|
| (Ex: AI Infra) | 加熱感/蓄積期/ピークアウト | 流入継続/利確売り/ショートカバー | Smart Money動向 |
| (Ex: Defensives) | 蓄積期 | 静かに流入 | レイトサイクル準備 |
| (Ex: Commodities) | 蓄積期/調整 | ... | 株式との連動性 |
| (Ex: Crypto) | ... | ... | 流動性プロキシとして |

*(Narrative paragraph first, then summarize in table)*

---

### Ⅲ. まとめ (Outlook & Key Catalysts)

- **Main Scenario**: [Bullish/Bearish/Neutral] - トリガーレベル明示（例：S&P500 5,200突破で上目線加速）
- **Risk Scenario**: 逆シナリオと発動条件（例：VIX 20超で調整リスク顕在化）
- **Key Catalysts (今後1-2週間)**:
  - 決算発表スケジュール（注目銘柄）
  - 経済指標（CPI, 雇用統計, PMI等）
  - FRB/中銀イベント
  - 地政学リスク監視ポイント
{earnings_section}
"""
    
    try:
        model = genai.GenerativeModel("gemini-3-flash-preview") # Use 3 Flash Preview
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"レポート生成エラー: {str(e)}"


def generate_company_summary_ja(ticker: str, english_summary: str) -> str:
    """
    英語の企業概要を日本語に翻訳・要約します。
    
    Args:
        ticker: 銘柄コード
        english_summary: 英語の企業概要
    
    Returns:
        日本語の企業概要
    """
    if not GEMINI_AVAILABLE or not english_summary:
        return english_summary
    
    # APIキーを設定
    from src.settings_storage import get_gemini_api_key
    api_key = get_gemini_api_key()
    if not api_key:
        return english_summary
    
    genai.configure(api_key=api_key)
    
    prompt = f"""
以下の企業概要を、投資家向けに日本語で簡潔に要約してください（3-5文程度）。
主な事業内容、競争優位性、注目すべきポイントを含めてください。

銘柄: {ticker}
英語概要:
{english_summary}
"""
    
    try:
        model = genai.GenerativeModel("gemini-3-flash-preview")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return english_summary

