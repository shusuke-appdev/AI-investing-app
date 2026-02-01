from typing import Optional
import google.generativeai as genai
from .analysis import get_macro_context, get_sector_performance, get_theme_exposure_analysis, get_holdings_news
from .technical import analyze_market_technicals

def generate_portfolio_advice(
    analysis: dict,
    market_sentiment: str = "中立",
    option_summary: Optional[str] = None,
    include_macro: bool = True,
    include_news: bool = True
) -> str:
    """
    AIによる包括的なポートフォリオアドバイスを生成します。
    """
    model = genai.GenerativeModel("gemini-3-flash-preview")
    
    # ポートフォリオサマリー構築
    holdings_text = []
    for h in analysis["holdings"]:
        tech = h.get("technical")
        tech_str = f"テクニカル: {tech.overall_signal} (RSI: {tech.rsi:.1f})" if tech else "テクニカル: N/A"
        pnl = f"損益: {h['pnl_pct']:+.1f}%" if h.get('pnl_pct') is not None else ""
        holdings_text.append(
            f"- {h['ticker']} ({h['name']}): ${h['current_price']:.2f} x {h['shares']:.1f}株 = ${h['value']:,.0f} "
            f"({h['weight']:.1f}%) | セクター: {h.get('sector', '不明')} | {tech_str} | {pnl}"
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
                    f"- {ticker}: {data['signal']} (RSI: {data['rsi']:.1f}, MACD: {data['macd']})"
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
    
    prompt = f"""あなたは経験豊富なポートフォリオマネージャー兼マクロストラテジストです。
以下の情報に基づいて、包括的で具体的な投資アドバイスを提供してください。

【ポートフォリオ概要】
総資産: ${analysis['total_value']:,.0f}
銘柄数: {analysis['num_holdings']}

【保有銘柄詳細】
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
- 分散度スコア、リスク/リターン効率、セクター/テーマバランス
- 現在の市場環境との適合度

## 2. マクロ環境分析
- 金利・為替・商品市況がポートフォリオに与える影響
- 注目すべきマクロリスク要因

## 3. 市場テクニカル分析
- 主要指数（SPY/QQQ/IWM）のトレンド判断
- エントリー/イグジットタイミングの示唆

## 4. セクター/テーマ別分析
- 資金フロー（どのセクター/テーマに資金が向かっているか）
- ポートフォリオのポジショニング評価

## 5. 銘柄別アクション（必ず全銘柄について言及）
各銘柄について以下を明記:
- アクション: 買い増し / 保持 / 削減 / 売却
- 目標比率（現在→推奨）
- 理由（テクニカル/ファンダメンタルズ/マクロ要因を踏まえて）

## 6. 具体的リバランス提案
- 削減すべき銘柄とその金額/株数
- 追加すべき銘柄とその金額/株数
- 追加検討すべき新規銘柄（あれば、ティッカーと理由）

## 7. リスク管理
- 主要リスク要因（3つ程度）
- ヘッジ戦略の提案

## 8. タイミング
- 短期（1-2週間）の見通し
- 中期（1-3ヶ月）の見通し

【ルール】
- 日本語、だ・である調
- 具体的な数字（金額、株数、比率）を必ず使う
- 曖昧な表現を避け、明確なアクションを提示
- 投資判断は自己責任である旨を最後に注記
"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"アドバイス生成エラー: {str(e)}"
