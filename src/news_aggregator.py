"""
ニュース集約モジュール
複数ソースからニュースを収集・統合します。
"""
from datetime import datetime, timedelta
from typing import Optional
import hashlib


def _generate_news_id(title: str, link: str) -> str:
    """ニュースの一意IDを生成（重複排除用）"""
    content = f"{title}:{link}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def get_gnews_articles(
    topic: str = "BUSINESS",
    query: Optional[str] = None,
    max_results: int = 15,
    language: str = "en",
    country: str = "US"
) -> list[dict]:
    """
    GNewsライブラリ経由でGoogle Newsから記事を取得
    
    Args:
        topic: トピック (BUSINESS, TECHNOLOGY, WORLD, etc.)
        query: 検索キーワード（Noneの場合はトピックのみ）
        max_results: 最大取得件数
        language: 言語コード
        country: 国コード
    
    Returns:
        [{"title", "summary", "source", "published", "link", "category"}, ...]
    """
    try:
        from gnews import GNews
        
        gn = GNews(
            language=language,
            country=country,
            max_results=max_results
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
        for article in (articles or []):
            pub_date = article.get("published date", "")
            # GNewsの日付形式: "Mon, 01 Jan 2024 12:00:00 GMT"
            try:
                if pub_date:
                    dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                    pub_str = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    pub_str = ""
            except Exception:
                pub_str = pub_date[:16] if pub_date else ""
            
            results.append({
                "title": article.get("title", ""),
                "summary": article.get("description", ""),
                "source": "GNews",
                "publisher": article.get("publisher", {}).get("title", ""),
                "published": pub_str,
                "link": article.get("url", ""),
                "category": query if query else topic,
            })
        
        return results
        
    except ImportError:
        print("gnews library not installed. Run: pip install gnews")
        return []
    except Exception as e:
        print(f"GNews fetch error: {e}")
        return []


def get_aggregated_news(
    categories: list[str] = None,
    keywords: list[str] = None,
    max_per_source: int = 10,
    max_total: int = 80
) -> list[dict]:
    """
    複数ソースからニュースを集約
    
    Args:
        categories: 取得するカテゴリ (BUSINESS, TECHNOLOGY, WORLD)
        keywords: 検索キーワード (Fed, FOMC, inflation, Oil, Bitcoin, etc.)
        max_per_source: 各ソース/カテゴリあたりの最大件数
        max_total: 合計最大件数
    
    Returns:
        重複排除済みのニュースリスト
    """
    if categories is None:
        categories = ["BUSINESS", "TECHNOLOGY"]
    
    if keywords is None:
        keywords = [
            # マクロ・政策
            "Federal Reserve", "FOMC", "inflation", "Treasury yields",
            # コモディティ
            "crude oil", "gold prices", "commodities",
            # 暗号資産
            "Bitcoin", "cryptocurrency",
            # 市場全般
            "stock market", "S&P 500", "Nasdaq",
        ]
    
    all_news = []
    seen_ids = set()
    
    # 1. カテゴリ別取得
    for category in categories:
        articles = get_gnews_articles(
            topic=category,
            max_results=max_per_source
        )
        for article in articles:
            news_id = _generate_news_id(article["title"], article["link"])
            if news_id not in seen_ids:
                article["news_id"] = news_id
                all_news.append(article)
                seen_ids.add(news_id)
    
    # 2. キーワード別取得
    for keyword in keywords:
        articles = get_gnews_articles(
            query=keyword,
            max_results=max(3, max_per_source // 3)  # キーワードは少なめ
        )
        for article in articles:
            news_id = _generate_news_id(article["title"], article["link"])
            if news_id not in seen_ids:
                article["news_id"] = news_id
                all_news.append(article)
                seen_ids.add(news_id)
    
    # 3. 日付順ソート（新しい順）
    all_news.sort(key=lambda x: x.get("published", ""), reverse=True)
    
    # 4. 上限適用
    return all_news[:max_total]


def merge_with_yfinance_news(
    gnews_articles: list[dict],
    yfinance_articles: list[dict],
    max_total: int = 80
) -> list[dict]:
    """
    GNewsとyfinanceのニュースを統合（重複排除付き）
    
    Args:
        gnews_articles: get_aggregated_news()の結果
        yfinance_articles: yfinance経由のニュース
        max_total: 合計最大件数
    
    Returns:
        統合済みニュースリスト
    """
    seen_ids = set()
    merged = []
    
    # yfinanceを優先（ティッカー紐付けがあるため）
    for article in yfinance_articles:
        news_id = _generate_news_id(
            article.get("title", ""),
            article.get("link", "")
        )
        if news_id not in seen_ids:
            article["news_id"] = news_id
            article["source"] = article.get("source", "YFinance")
            merged.append(article)
            seen_ids.add(news_id)
    
    # GNewsを追加
    for article in gnews_articles:
        news_id = article.get("news_id") or _generate_news_id(
            article.get("title", ""),
            article.get("link", "")
        )
        if news_id not in seen_ids:
            merged.append(article)
            seen_ids.add(news_id)
    
    # 日付順ソート
    merged.sort(key=lambda x: x.get("published", ""), reverse=True)
    
    return merged[:max_total]
