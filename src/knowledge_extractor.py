"""
参照知識抽出モジュール
テキスト、ファイル、URL、YouTubeからコンテンツを抽出し、要約を生成します。
"""

import re
from pathlib import Path
from typing import Optional

# Gemini API
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def extract_from_text(text: str) -> str:
    """
    テキストからコンテンツを抽出します。

    Args:
        text: 入力テキスト

    Returns:
        クリーンアップされたテキスト
    """
    # 余分な空白を削除
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_from_file(file_content: bytes, file_name: str) -> str:
    """
    ファイルからコンテンツを抽出します。

    Args:
        file_content: ファイルのバイナリコンテンツ
        file_name: ファイル名

    Returns:
        抽出されたテキスト
    """
    ext = Path(file_name).suffix.lower()

    if ext == ".txt":
        # テキストファイル
        try:
            return file_content.decode("utf-8")
        except UnicodeDecodeError:
            return file_content.decode("cp932", errors="ignore")

    elif ext == ".pdf":
        # PDFファイル
        try:
            import io

            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(file_content))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            return "\n".join(text_parts)
        except ImportError:
            return "[PDF読み取りにはPyPDF2が必要です]"
        except Exception as e:
            return f"[PDF読み取りエラー: {e}]"

    elif ext in [".md", ".csv", ".json"]:
        # その他のテキスト系ファイル
        try:
            return file_content.decode("utf-8")
        except UnicodeDecodeError:
            return file_content.decode("cp932", errors="ignore")

    else:
        return f"[未対応のファイル形式: {ext}]"


def extract_from_youtube(video_url: str) -> str:
    """
    YouTube動画からトランスクリプトを抽出します。

    Args:
        video_url: YouTube動画のURL

    Returns:
        トランスクリプトテキスト
    """
    # Video IDを抽出
    video_id = _extract_youtube_video_id(video_url)
    if not video_id:
        return "[無効なYouTube URLです]"

    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        # 日本語 → 英語 → 自動生成の順で試行
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        transcript = None
        for lang in ["ja", "en"]:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except Exception:
                continue

        if not transcript:
            # 自動生成を取得
            transcript = transcript_list.find_generated_transcript(["ja", "en"])

        if transcript:
            entries = transcript.fetch()
            text_parts = [entry["text"] for entry in entries]
            return " ".join(text_parts)

        return "[トランスクリプトが見つかりません]"

    except ImportError:
        return "[YouTube機能にはyoutube-transcript-apiが必要です]"
    except Exception as e:
        return f"[YouTubeトランスクリプト取得エラー: {e}]"


def _extract_youtube_video_id(url: str) -> Optional[str]:
    """URLからYouTube Video IDを抽出"""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",  # IDのみの場合
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_from_url(url: str) -> str:
    """
    URLからWebページコンテンツを抽出します。

    Args:
        url: WebページのURL

    Returns:
        抽出されたテキスト
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # 不要な要素を削除
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # メインコンテンツを抽出
        main_content = soup.find("main") or soup.find("article") or soup.find("body")

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
            # 過度な改行を削除
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text[:15000]  # 最大15KB

        return "[コンテンツを抽出できませんでした]"

    except ImportError:
        return "[URL機能にはrequestsとbeautifulsoup4が必要です]"
    except Exception as e:
        return f"[URL取得エラー: {e}]"


def summarize_content(content: str, source_type: str = "text") -> str:
    """
    Gemini APIを使用してコンテンツを要約します。

    Args:
        content: 要約するコンテンツ
        source_type: ソースの種類

    Returns:
        要約テキスト
    """
    if not GEMINI_AVAILABLE:
        # フォールバック: 冒頭を返す
        return content[:500] + "..." if len(content) > 500 else content

    # APIキーを取得
    try:
        from src.settings_storage import get_gemini_api_key

        api_key = get_gemini_api_key()
        if not api_key:
            return content[:500] + "..." if len(content) > 500 else content

        genai.configure(api_key=api_key)
    except Exception:
        return content[:500] + "..." if len(content) > 500 else content

    source_label = {
        "text": "テキスト",
        "file": "ファイル",
        "youtube": "YouTube動画のトランスクリプト",
        "url": "Webページ",
    }.get(source_type, source_type)

    prompt = f"""以下は{source_label}から抽出されたコンテンツです。
投資・経済分析に関連する重要なポイントを抽出し、3-5文で要約してください。
特に、市場動向、企業業績、マクロ経済、投資テーマに関する情報を重視してください。

コンテンツ:
{content[:8000]}

要約（日本語で）:"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        # エラー時はフォールバック
        return content[:500] + "..." if len(content) > 500 else content


def generate_title(content: str, source_type: str) -> str:
    """
    コンテンツからタイトルを自動生成します。

    Args:
        content: コンテンツ
        source_type: ソースの種類

    Returns:
        生成されたタイトル
    """
    if not GEMINI_AVAILABLE:
        # フォールバック: 冒頭を使用
        title = content[:50].replace("\n", " ").strip()
        return title + "..." if len(content) > 50 else title

    try:
        from src.settings_storage import get_gemini_api_key

        api_key = get_gemini_api_key()
        if not api_key:
            title = content[:50].replace("\n", " ").strip()
            return title + "..." if len(content) > 50 else title

        genai.configure(api_key=api_key)
    except Exception:
        title = content[:50].replace("\n", " ").strip()
        return title + "..." if len(content) > 50 else title

    prompt = f"""以下のコンテンツに適切な短いタイトル（20文字以内）を付けてください。
投資・経済に関連する内容の場合、その観点を反映させてください。

コンテンツ:
{content[:2000]}

タイトル（20文字以内、日本語で）:"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        title = response.text.strip()
        # 余計な装飾を削除
        title = re.sub(r"^[「『]|[」』]$", "", title)
        return title[:30]
    except Exception:
        title = content[:50].replace("\n", " ").strip()
        return title + "..." if len(content) > 50 else title
