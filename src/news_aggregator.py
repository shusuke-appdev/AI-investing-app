"""
ニュース集約モジュール
複数ソースからニュースを収集・統合します。
"""

import concurrent.futures
import hashlib
from datetime import datetime, timedelta

from src.log_config import get_logger

logger = get_logger(__name__)


def _generate_news_id(title: str, link: str) -> str:
    """ニュースの一意IDを生成（重複排除用）"""
    content = f"{title}:{link}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def get_gnews_articles(
    topic: str = "BUSINESS",
    query: str | None = None,
    max_results: int = 15,
    language: str = "en",
    country: str = "US",
    period: str = "2d",  # 直近2日に限定（デフォルト）
) -> list[dict]:
    """
    GNewsライブラリ経由でGoogle Newsから記事を取得

    Args:
        topic: トピック (BUSINESS, TECHNOLOGY, WORLD, etc.)
        query: 検索キーワード（Noneの場合はトピックのみ）
        max_results: 最大取得件数
        language: 言語コード
        country: 国コード
        period: 取得期間 ("1d", "2d", "7d" など)

    Returns:
        [{"title", "summary", "source", "published", "published_dt", "link", "category"}, ...]
    """
    try:
        from gnews import GNews

        gn = GNews(
            language=language,
            country=country,
            max_results=max_results,
            period=period,  # 直近の記事に限定
        )

        if query:
            articles = gn.get_news(query)
        else:
            # トピック別取得
            topic_map = {
                "BUSINESS": gn.get_news_by_topic,
                "TECHNOLOGY": gn.get_news_by_topic,
                "WORLD": gn.get_news_by_topic,
            }
            if topic in topic_map:
                articles = gn.get_news_by_topic(topic)
            else:
                articles = gn.get_news(topic)

        results = []
        for article in articles or []:
            pub_date = article.get("published date", "")
            pub_dt = None
            pub_str = ""

            # GNewsの日付形式: "Mon, 01 Jan 2024 12:00:00 GMT"
            if pub_date:
                try:
                    pub_dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                    pub_str = pub_dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    # タイムゾーン部分が異なる場合のフォールバック
                    try:
                        pub_dt = datetime.strptime(
                            pub_date[:25], "%a, %d %b %Y %H:%M:%S"
                        )
                        pub_str = pub_dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pub_str = pub_date[:16] if pub_date else ""

            results.append(
                {
                    "title": article.get("title", ""),
                    "summary": article.get("description", ""),
                    "source": "GNews",
                    "publisher": article.get("publisher", {}).get("title", ""),
                    "published": pub_str,
                    "published_dt": pub_dt,  # datetime オブジェクトを保持（フィルタリング用）
                    "link": article.get("url", ""),
                    "category": query if query else topic,
                }
            )

        return results

    except ImportError:
        logger.info("gnews library not installed. Run: pip install gnews")
        return []
    except Exception as e:
        logger.error(f"GNews fetch error: {e}")
        return []


def _get_news_cutoff_time(hours: int = 48) -> datetime:
    """
    ニュースフィルタリング用のカットオフ時刻を計算。
    市場営業日を考慮し、週末は金曜日の記事も含めるように調整。

    Args:
        hours: 何時間前までの記事を許容するか

    Returns:
        カットオフ時刻（これより古い記事は除外）
    """
    now = datetime.now()
    weekday = now.weekday()

    # 週末の場合は金曜日からカウント
    if weekday == 5:  # 土曜
        # 金曜夜から48時間 = 木曜夜まで許容
        hours += 24
    elif weekday == 6:  # 日曜
        # 金曜夜から48時間 + 土曜分
        hours += 48
    elif weekday == 0:  # 月曜の場合、金曜の記事も含める
        hours += 24

    return now - timedelta(hours=hours)


def get_aggregated_news(
    categories: list[str] | None = None,
    keywords: list[str] | None = None,
    dynamic_keywords: list[str] | None = None,
    max_per_source: int = 10,
    max_total: int = 80,
    market_type: str = "US",
    filter_hours: int = 48,  # 48時間以内の記事のみ
) -> list[dict]:
    """
    複数ソースからニュースを集約

    Args:
        categories: 取得するカテゴリ (BUSINESS, TECHNOLOGY, WORLD)
        keywords: 静的な検索キーワード
        dynamic_keywords: 動的に生成された検索キーワード
        max_per_source: 各ソース/カテゴリあたりの最大件数
        max_total: 合計最大件数
        market_type: "US" または "JP"
        filter_hours: 何時間以内の記事を対象とするか（デフォルト48時間）

    Returns:
        重複排除・日付フィルタリング済みのニュースリスト
    """
    # 市場に応じた言語・国設定
    if market_type == "JP":
        language, country = "ja", "JP"
    else:
        language, country = "en", "US"

    if categories is None:
        categories = ["BUSINESS", "TECHNOLOGY"]

    if keywords is None:
        if market_type == "JP":
            keywords = [
                # マクロ・政策
                "日銀",
                "金融政策",
                "円安",
                "インフレ",
                # 市場
                "日経平均",
                "TOPIX",
                "東証",
                # コモディティ・為替
                "原油価格",
                "ドル円",
                # 企業・セクター
                "決算",
                "半導体",
                "自動車",
            ]
        else:
            keywords = [
                # マクロ・政策
                "Federal Reserve",
                "FOMC",
                "inflation",
                "Treasury yields",
                # コモディティ
                "crude oil",
                "gold prices",
                "commodities",
                # 暗号資産
                "Bitcoin",
                "cryptocurrency",
                # 市場全般
                "stock market",
                "S&P 500",
                "Nasdaq",
            ]

    # 動的キーワードがある場合は追加
    if dynamic_keywords:
        # 重複を排除しつつリストの先頭に追加して優先度を高くする
        keywords = list(dict.fromkeys(dynamic_keywords + keywords))

    all_news = []
    seen_ids = set()
    cutoff_time = _get_news_cutoff_time(filter_hours)

    # 並行処理用タスクリストの構築
    tasks = []

    # 1. カテゴリ別取得タスク
    for category in categories:
        tasks.append(
            {
                "topic": category,
                "max_results": max_per_source,
                "language": language,
                "country": country,
                "period": "2d",
            }
        )

    # 2. キーワード別取得タスク
    for keyword in keywords:
        tasks.append(
            {
                "query": keyword,
                "max_results": max(3, max_per_source // 3),
                "language": language,
                "country": country,
                "period": "2d",
            }
        )

    # ワーカースレッド用のフェッチ関数
    def _fetch_news(kwargs_dict: dict) -> list[dict]:
        return get_gnews_articles(**kwargs_dict)

    # ThreadPoolExecutorを用いた並行取得（GNewsへのリクエストを並列化して待機時間を短縮）
    max_workers = min(10, len(tasks)) if tasks else 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(_fetch_news, t): t for t in tasks}
        for future in concurrent.futures.as_completed(future_to_task):
            try:
                articles = future.result()
                for article in articles:
                    # 事後フィルタリング: 発行日時がカットオフより新しいもののみ
                    pub_dt = article.get("published_dt")
                    if pub_dt and pub_dt < cutoff_time:
                        continue

                    news_id = _generate_news_id(article["title"], article["link"])
                    if news_id not in seen_ids:
                        article["news_id"] = news_id
                        all_news.append(article)
                        seen_ids.add(news_id)
            except Exception as e:
                logger.error(f"News fetch error in executor: {e}")

    # 3. 日付順ソート（新しい順）
    all_news.sort(key=lambda x: x.get("published", ""), reverse=True)

    # 4. 上限適用
    return all_news[:max_total]


def merge_with_finnhub_news(
    gnews_articles: list[dict], finnhub_articles: list[dict], max_total: int = 80
) -> list[dict]:
    """
    GNewsとFinnhubのニュースを統合（重複排除付き）

    Args:
        gnews_articles: get_aggregated_news()の結果
        finnhub_articles: Finnhub経由のニュース
        max_total: 合計最大件数

    Returns:
        統合済みニュースリスト
    """
    seen_ids = set()
    merged = []

    # Finnhubを優先（個別銘柄・公式ニュースのため）
    for article in finnhub_articles:
        # 重複チェック用ID生成
        news_id = _generate_news_id(article.get("title", ""), article.get("link", ""))
        if news_id not in seen_ids:
            article["news_id"] = news_id
            # Sourceが空ならFinnhubとする（通常は提供元が入る）
            if not article.get("source"):
                article["source"] = "Finnhub"

            merged.append(article)
            seen_ids.add(news_id)

    # GNewsを追加
    for article in gnews_articles:
        news_id = article.get("news_id") or _generate_news_id(
            article.get("title", ""), article.get("link", "")
        )
        if news_id not in seen_ids:
            merged.append(article)
            seen_ids.add(news_id)

    # 日付順ソート (YYYY-MM-DD HH:MM 文字列比較)
    merged.sort(key=lambda x: x.get("published", ""), reverse=True)

    return merged[:max_total]
