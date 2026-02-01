"""
銘柄分析AIモジュール
RLM風プロンプトを使用した詳細な銘柄分析を提供します。
"""
from typing import Optional
import google.generativeai as genai

# 分析用モデル
_model = None


def _get_model():
    """モデルインスタンスを取得"""
    global _model
    if _model is None:
        _model = genai.GenerativeModel("gemini-3-flash-preview")
    return _model


def analyze_stock(
    ticker: str,
    stock_info: dict,
    historical_data: Optional[dict] = None,
    news_headlines: Optional[list[str]] = None
) -> str:
    """
    銘柄の詳細分析を生成します。
    
    Args:
        ticker: 銘柄コード
        stock_info: yfinanceから取得した銘柄情報
        historical_data: 過去の株価データ
        news_headlines: 関連ニュースのヘッドライン
    
    Returns:
        分析レポート（マークダウン形式）
    """
    model = _get_model()
    
    # 基本情報の抽出
    company_name = stock_info.get("longName", ticker)
    sector = stock_info.get("sector", "不明")
    industry = stock_info.get("industry", "不明")
    market_cap = stock_info.get("marketCap", 0)
    pe_ratio = stock_info.get("trailingPE", "N/A")
    forward_pe = stock_info.get("forwardPE", "N/A")
    price = stock_info.get("currentPrice", stock_info.get("regularMarketPrice", 0))
    target_price = stock_info.get("targetMeanPrice", "N/A")
    
    # プロンプト構築
    prompt = f"""あなたはエクイティリサーチアナリストです。以下の銘柄について、客観的かつ批判的な分析を行ってください。

【銘柄情報】
- ティッカー: {ticker}
- 企業名: {company_name}
- セクター: {sector}
- 業種: {industry}
- 時価総額: ${market_cap/1e9:.2f}B
- 現在株価: ${price:.2f}
- PER (直近): {pe_ratio}
- PER (予想): {forward_pe}
- アナリスト目標株価: ${target_price}

【関連ニュース】
{chr(10).join(news_headlines[:5]) if news_headlines else "ニュースなし"}

【分析指示】
1. **投資判断**: 買い / 中立 / 売り のいずれかを明示
2. **強気シナリオ** (Bull Case): この銘柄が上昇する根拠を2-3点
3. **弱気シナリオ** (Bear Case): この銘柄が下落するリスクを2-3点（Devil's Advocate視点）
4. **バリュエーション評価**: 現在の株価が割高か割安かを判断
5. **カタリスト**: 株価を動かしうる今後のイベント

【出力ルール】
- 日本語で回答
- だ・である調
- 各セクションは見出しを付ける
- 不確実な情報は「可能性がある」「推測される」と明記
- 投資アドバイスではなく情報提供であることを最後に注記
"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"分析エラー: {str(e)}"


def get_quick_summary(ticker: str, stock_info: dict) -> str:
    """
    銘柄のクイックサマリーを生成します。
    
    Args:
        ticker: 銘柄コード
        stock_info: yfinanceから取得した銘柄情報
    
    Returns:
        1-2行のサマリー
    """
    model = _get_model()
    
    company_name = stock_info.get("longName", ticker)
    sector = stock_info.get("sector", "不明")
    market_cap = stock_info.get("marketCap", 0)
    pe_ratio = stock_info.get("trailingPE", "N/A")
    
    prompt = f"""以下の銘柄について、1-2文で簡潔に説明してください。

ティッカー: {ticker}
企業名: {company_name}
セクター: {sector}
時価総額: ${market_cap/1e9:.2f}B
PER: {pe_ratio}

日本語で、だ・である調で回答。"""
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"{company_name} ({ticker}) - {sector}"
