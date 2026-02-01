from typing import Optional
import google.generativeai as genai
from .analysis import get_macro_context, get_sector_performance, get_theme_exposure_analysis, get_holdings_news
from .technical import analyze_market_technicals, analyze_technical, get_technical_summary_for_ai

def generate_portfolio_advice(
    analysis: dict,
    market_sentiment: str = "中立",
    option_summary: Optional[str] = None,
    include_macro: bool = True,
    include_news: bool = True
) -> str:
    """
    AIによる包括的なポートフォリオアドバイスを生成します。
    テクニカル分析に基づく具体的な売買判断（数量・タイミング）を含む。
    """
    model = genai.GenerativeModel("gemini-3-flash-preview")
    
    # ポートフォリオサマリー構築（テクニカル詳細を拡充）
    holdings_text = []
    technical_summaries = []
    
    for h in analysis["holdings"]:
        tech = h.get("technical")
        if tech:
            tech_str = (
                f"テクニカル: {tech.overall_signal} (スコア: {tech.overall_score:+d}) | "
                f"RSI: {tech.rsi:.1f} ({tech.rsi_signal}) | "
                f"MACD: {tech.macd_signal} | "
                f"逆張り: {tech.contrarian_signal}"
            )
            # 逆張り買いゾーン情報
            zone_str = f"買いゾーン: ${tech.contrarian_buy_zone[0]:.2f}-${tech.contrarian_buy_zone[1]:.2f}"
            support_str = f"サポート: ${tech.support_price:.2f}"
        else:
            tech_str = "テクニカル: N/A"
            zone_str = ""
            support_str = ""
        
        pnl = f"損益: {h['pnl_pct']:+.1f}%" if h.get('pnl_pct') is not None else ""
        
        holdings_text.append(
            f"- {h['ticker']} ({h['name']}): ${h['current_price']:.2f} x {h['shares']:.1f}株 = ${h['value']:,.0f} "
            f"({h['weight']:.1f}%) | セクター: {h.get('sector', '不明')} | {pnl}\n"
            f"  {tech_str}\n"
            f"  {zone_str} | {support_str}"
        )
    
    # マクロ分析
    macro_text = ""
    market_tech_text = ""
    sector_text = ""
    theme_text = ""
    news_text = ""
    
    if include_macro:
        # マクロ環境
        macro = get_macro_context()
        macro_lines = ["【マクロ環境】"]
        
        # 指数
        for name, data in macro.get("indices", {}).items():
            macro_lines.append(f"- {name}: {data.get('change', 0):+.2f}%")
        
        # 金利
        rate_parts = []
        for name, data in macro.get("rates", {}).items():
            rate_parts.append(f"{name}: {data.get('price', 0):.2f}%")
        if rate_parts:
            macro_lines.append(f"- 金利: {', '.join(rate_parts)}")
        
        # 商品
        for name, data in macro.get("commodities", {}).items():
            macro_lines.append(f"- {name}: {data.get('change', 0):+.2f}%")
        
        macro_text = "\n".join(macro_lines)
        
        # 市場テクニカル
        market_tech = analyze_market_technicals()
        if market_tech:
            tech_lines = ["【市場テクニカル分析】"]
            for ticker, data in market_tech.items():
                tech_lines.append(
                    f"- {ticker}: {data['signal']} (RSI: {data['rsi']:.1f}, MACD: {data['macd']}, トレンド: {data.get('trend', 'N/A')})"
                )
            market_tech_text = "\n".join(tech_lines)
        
        # セクターパフォーマンス
        sectors = get_sector_performance()
        if sectors:
            sorted_sectors = sorted(sectors.items(), key=lambda x: x[1].get("change_1m", 0), reverse=True)
            sector_lines = ["【セクター別1ヶ月パフォーマンス】"]
            for sector, data in sorted_sectors[:5]:
                sector_lines.append(f"- {sector}: {data['change_1m']:+.1f}%")
            sector_lines.append("...")
            for sector, data in sorted_sectors[-3:]:
                sector_lines.append(f"- {sector}: {data['change_1m']:+.1f}%")
            sector_text = "\n".join(sector_lines)
        
        # テーマエクスポージャー
        themes = get_theme_exposure_analysis(analysis["holdings"])
        if themes:
            theme_lines = ["【テーマ別エクスポージャー】"]
            for theme, data in list(themes.items())[:5]:
                theme_lines.append(f"- {theme}: ${data['value']:,.0f} ({data['weight']:.1f}%)")
            theme_text = "\n".join(theme_lines)
    
    if include_news:
        news = get_holdings_news(analysis["holdings"])
        if news:
            news_lines = ["【保有銘柄関連ニュース】"]
            for n in news[:8]:
                news_lines.append(f"- [{n.get('ticker', '')}] {n.get('title', '')}")
            news_text = "\n".join(news_lines)
    
    prompt = f"""あなたは経験豊富なポートフォリオマネージャー兼テクニカルアナリストです。
以下の情報に基づいて、**テクニカル分析を重視した具体的な売買アドバイス**を提供してください。

【ポートフォリオ概要】
総資産: ${analysis['total_value']:,.0f}
銘柄数: {analysis['num_holdings']}

【保有銘柄詳細（テクニカル分析含む）】
{chr(10).join(holdings_text)}

{macro_text}

{market_tech_text}

{sector_text}

{theme_text}

【市場センチメント】
オプション市場: {market_sentiment}
{f"詳細: {option_summary}" if option_summary else ""}

{news_text}

【出力形式 - 以下の構成で詳細に分析】

## 1. ポートフォリオ総合評価 (0-100点)
- 分散度、リスク/リターン効率、テクニカル状態の総合評価
- 現在の市場環境との適合度

## 2. 市場テクニカル環境
- SPY/QQQ/IWMのトレンド判断
- 全体的なリスクオン/オフの判断
- 今週〜今月のエントリー/イグジット推奨タイミング

## 3. 銘柄別 売買アクション（全銘柄について必ず言及）

各銘柄について以下のフォーマットで明記:

### [ティッカー] [銘柄名]
- **アクション**: 買い増し / 保持 / 一部売却 / 全売却
- **数量**: 具体的な株数または金額（例: "5株追加" "50%削減" "$1,000分購入"）
- **タイミング**: 
  - 即時 / 逆張り買いゾーン到達時 / RSI30以下到達時 / 様子見
  - 具体的な価格水準（例: "$150以下で買い増し"）
- **損切りライン**: 価格（例: "サポート$140割れで損切り"）
- **根拠**: テクニカル指標に基づく理由

## 4. 新規購入候補（任意）
- テクニカル的に魅力的な銘柄があれば、ティッカーと理由

## 5. リスク管理
- 主要リスク（3つ程度）
- ポートフォリオ全体の損切りルール

## 6. 今後1ヶ月のアクションプラン
- 週ごとの推奨アクション

【ルール】
- 日本語、だ・である調
- **具体的な数字（株数、金額、価格水準）を必ず使う**
- テクニカル指標（RSI、MACD、サポート/レジスタンス）を根拠に使う
- 曖昧な表現を避け、明確なアクションを提示
- 投資判断は自己責任である旨を最後に注記
"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"アドバイス生成エラー: {str(e)}"

