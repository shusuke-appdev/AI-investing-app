"""
動的クエリ生成サービス
市場の最新状況に基づいて、効果的なニュース検索キーワードをGemini APIを用いて生成します。
"""

import json
from datetime import datetime

from src.gemini_client import generate_content, get_gemini_client
from src.log_config import get_logger

logger = get_logger(__name__)


def generate_dynamic_search_queries(
    market_data: dict, num_queries: int = 5
) -> list[str]:
    """
    現在の市場データと日付から、GNews検索で有用なキーワードリストを動的に生成します。

    Args:
        market_data: 市場指数データ (主要な指数の現在値や変化率など)
        num_queries: 生成するキーワードの最大数

    Returns:
        ニュース検索用キーワードのリスト (例: ["金利動向", "半導体 セクター", "円安 影響"])
    """
    if get_gemini_client() is None:
        logger.warning("Gemini API is not available. Using default static queries.")
        return []

    today_str = datetime.now().strftime("%Y-%m-%d")

    # 簡易な市場概況文字列の作成
    market_summary = ""
    for name, data in market_data.items():
        if isinstance(data, dict):
            price = data.get("price", "N/A")
            change = data.get("change_percent", "N/A")
            market_summary += f"- {name}: {price} ({change}%)\n"

    prompt = f"""
あなたはプロの金融情報アナリストです。
現在の市場の中心的テーマやマクロ環境を俯瞰し、Google Newsで現在最も調べるべき金融・報道ニュースの検索キーワード（日本語）を {num_queries} つ生成してください。

【前提情報】
本日の日付: {today_str}
直近の市場データ:
{market_summary}

【指示】
- 現在の市場（日本市場および米国市場）を動かしている主要テーマ（例：金利動向、特定セクターの動向、政策発表、地政学リスク等）に焦点を当ててください。
- Google Newsでの検索クエリとしてそのまま使える、短くかつ具体的なキーワード句にしてください。（例: "日銀 金融政策", "米国 インフレ懸念", "半導体 決算" など）
- 単純な「日経平均」などの固定語ではなく、今起こっている事象の文脈を反映したキーワードが望ましいです。
- 出力は必ず以下のJSON形式の配列のみとしてください。他の説明やマークダウン記法(```json など)を含めないでください。

["キーワード1", "キーワード2", "キーワード3"]
"""

    result = generate_content(prompt)
    if not result:
        return []

    try:
        # 応答からJSON文字列の抽出（フォーマット崩れへの防御的処理）
        text = result.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        queries = json.loads(text)
        if isinstance(queries, list):
            # 要素から不要な空白を取り除く
            return [str(q).strip() for q in queries[:num_queries]]
        else:
            logger.error(f"Unexpected JSON format from Gemini: {text}")
            return []

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini response: {e}\nResponse: {result}")
        return []
    except Exception as e:
        logger.error(f"Error generating dynamic queries with Gemini: {e}")
        return []
