"""
銘柄分析AIモジュール
テクニカル分析を統合した詳細な銘柄分析を提供します。
"""
from typing import Optional
import google.generativeai as genai
from src.advisor.technical import analyze_technical, get_technical_summary_for_ai

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
    銘柄の詳細分析を生成します（テクニカル分析統合版）。
    
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
    
    # テクニカル分析を取得
    technical_summary = get_technical_summary_for_ai(ticker)
    
    # プロンプト構築
    prompt = f"""あなたはエクイティリサーチアナリスト兼テクニカルアナリストです。
以下の銘柄について、ファンダメンタルズとテクニカル両面から客観的かつ批判的な分析を行ってください。

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

{technical_summary}

【関連ニュース】
{chr(10).join(news_headlines[:5]) if news_headlines else "ニュースなし"}

【分析指示】

## 1. 投資判断
買い / 中立 / 売り のいずれかを明示し、その根拠を1行で

## 2. テクニカル分析
- 現在のトレンド評価
- エントリーポイント（具体的な価格水準）
- 逆張り買いゾーンの評価
- 損切りライン（サポート割れなど）

## 3. ファンダメンタルズ
- バリュエーション評価（割高/割安）
- 成長性・収益性の評価

## 4. Bull Case（強気シナリオ）
- 上昇要因を2-3点

## 5. Bear Case（弱気シナリオ）
- 下落リスクを2-3点（Devil's Advocate視点）

## 6. 推奨アクション
- 具体的な売買タイミング
- 買い増し/利確の価格水準

【出力ルール】
- 日本語で回答
- だ・である調
- 具体的な数字（価格、比率）を使う
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
