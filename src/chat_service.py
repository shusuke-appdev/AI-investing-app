"""
チャットサービスモジュール
Gemini APIを使用した対話型チャット機能を提供します。
"""
from typing import Optional
import google.generativeai as genai

# チャット用モデル
_chat_model = None
_chat_session = None


def get_chat_session(context: str = ""):
    """
    チャットセッションを取得または作成します。
    
    Args:
        context: チャットのコンテキスト（AIレポートなど）
    
    Returns:
        Geminiチャットセッション
    """
    global _chat_model, _chat_session
    
    if _chat_model is None:
        _chat_model = genai.GenerativeModel("gemini-3-flash-preview")
    
    if _chat_session is None:
        system_prompt = f"""あなたは金融市場のニュースと分析に精通したAIアナリストです。
以下のコンテキスト情報を参考に、ユーザーの質問に日本語で簡潔に回答してください。

【コンテキスト】
{context if context else "コンテキストなし"}

回答ルール:
- 簡潔かつ具体的に回答
- 不確実な情報は「推測です」と明記
- 投資アドバイスは控え、情報提供に徹する
"""
        _chat_session = _chat_model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ["了解しました。金融市場に関するご質問にお答えします。"]}
        ])
    
    return _chat_session


def reset_chat_session():
    """チャットセッションをリセットします。"""
    global _chat_session
    _chat_session = None


def send_message(message: str, context: str = "") -> str:
    """
    チャットメッセージを送信し、応答を取得します。
    
    Args:
        message: ユーザーメッセージ
        context: チャットコンテキスト
    
    Returns:
        AIの応答テキスト
    """
    try:
        session = get_chat_session(context)
        response = session.send_message(message)
        return response.text
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"
