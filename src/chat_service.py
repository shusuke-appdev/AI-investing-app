"""
チャットサービスモジュール
google.genai SDK を使用した対話型チャット機能を提供します。
セッション状態はReflex State または引数渡しで管理。
"""

from src.gemini_client import generate_content


def get_chat_session(
    history: list[dict] | None = None, context: str = ""
) -> list[dict]:
    """
    チャットセッション（履歴リスト）を取得または作成します。

    Args:
        history: 既存のチャット履歴（Noneの場合は新規作成）
        context: チャットのコンテキスト（AIレポートなど）

    Returns:
        チャット履歴のリスト
    """
    if history is not None:
        return history

    system_prompt = (
        "あなたは金融市場のニュースと分析に精通したAIアナリストです。\n"
        "以下のコンテキスト情報を参考に、ユーザーの質問に日本語で簡潔に回答してください。\n\n"
        f"【コンテキスト】\n{context if context else 'コンテキストなし'}\n\n"
        "回答ルール:\n"
        "- 簡潔かつ具体的に回答\n"
        "- 不確実な情報は「推測です」と明記\n"
        "- 投資アドバイスは控え、情報提供に徹する"
    )
    return [
        {"role": "user", "content": system_prompt},
        {
            "role": "model",
            "content": "了解しました。金融市場に関するご質問にお答えします。",
        },
    ]


def send_message(
    message: str, history: list[dict] | None = None, context: str = ""
) -> tuple[str, list[dict]]:
    """
    チャットメッセージを送信し、応答を取得します。

    Args:
        message: ユーザーメッセージ
        history: 既存の履歴（Noneの場合は新規作成）
        context: チャットコンテキスト

    Returns:
        (AIの応答テキスト, 更新された履歴)
    """
    chat_history = get_chat_session(history, context)

    # 履歴をプロンプトに組み込む（最新3往復分）
    history_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in chat_history[-6:]
    )

    prompt = (
        "以下は会話の履歴です。最後のUserメッセージに回答してください。\n\n"
        f"{history_text}\n\n"
        f"User: {message}"
    )

    result = generate_content(prompt)
    if result:
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "model", "content": result})
        return result, chat_history
    return "エラーが発生しました: Gemini APIが利用できません", chat_history


def get_market_chat_response(
    prompt: str, history: list[dict], system_context: str
) -> str:
    """市場分析チャット専用の応答生成"""
    system_prompt = (
        "あなたはウォール街の凄腕マクロクオンツアナリストです。\n"
        "プロフェッショナルで、無駄のないトーン（だ・である調）で回答してください。\n"
        "以下の市場分析レポート（コンテキスト）を前提知識として、ユーザーの質問に答えてください。\n\n"
        f"【コンテキスト】\n{system_context}\n\n"
        "回答ルール:\n"
        "- コンテキストの内容に関連する質問には、レポートの具体例や数値を引用して回答\n"
        "- 意見を聞かれた場合は、アナリストとしての客観的視点を述べる\n"
        "- 簡潔でデータドリブンな回答を心がける"
    )

    # 履歴をテキスト形式で構築
    history_text = f"System: {system_prompt}\n"
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"
    history_text += f"User: {prompt}"

    result = generate_content(history_text)
    if result:
        return result
    return "考えをまとめるのに失敗したようだ: Gemini APIエラー"
