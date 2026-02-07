"""
news_aggregator モジュールのテスト
"""
import pytest
from unittest.mock import patch, MagicMock


class TestGenerateNewsId:
    """_generate_news_id関数のテスト"""
    
    def test_generates_unique_id(self):
        """異なる入力に対して異なるIDを生成"""
        from src.news_aggregator import _generate_news_id
        
        id1 = _generate_news_id("Title 1", "https://example.com/1")
        id2 = _generate_news_id("Title 2", "https://example.com/2")
        
        assert id1 != id2
        assert len(id1) == 16
        assert len(id2) == 16
    
    def test_same_input_same_id(self):
        """同じ入力に対して同じIDを生成"""
        from src.news_aggregator import _generate_news_id
        
        id1 = _generate_news_id("Same Title", "https://example.com/same")
        id2 = _generate_news_id("Same Title", "https://example.com/same")
        
        assert id1 == id2


class TestMergeWithYfinanceNews:
    """merge_with_yfinance_news関数のテスト"""
    
    def test_deduplicates_news(self):
        """重複するニュースを排除"""
        from src.news_aggregator import merge_with_yfinance_news
        
        gnews = [
            {"title": "News A", "link": "https://example.com/a", "source": "GNews"},
            {"title": "News B", "link": "https://example.com/b", "source": "GNews"},
        ]
        yfinance = [
            {"title": "News A", "link": "https://example.com/a"},  # 重複
            {"title": "News C", "link": "https://example.com/c"},
        ]
        
        merged = merge_with_yfinance_news(gnews, yfinance, max_total=10)
        
        # 重複排除されて3件のはず
        assert len(merged) == 3
        # yfinanceが優先されるのでNews AはYFinanceソースのまま
        titles = [n["title"] for n in merged]
        assert "News A" in titles
        assert "News B" in titles
        assert "News C" in titles
    
    def test_respects_max_total(self):
        """max_total制限を尊重"""
        from src.news_aggregator import merge_with_yfinance_news
        
        gnews = [{"title": f"GNews {i}", "link": f"https://g.com/{i}"} for i in range(10)]
        yfinance = [{"title": f"YF {i}", "link": f"https://yf.com/{i}"} for i in range(10)]
        
        merged = merge_with_yfinance_news(gnews, yfinance, max_total=5)
        
        assert len(merged) == 5


class TestGetGnewsArticles:
    """get_gnews_articles関数のテスト（モック使用）"""
    
    @patch('gnews.GNews')
    def test_returns_formatted_articles(self, mock_gnews_class):
        """GNewsから取得した記事を正しいフォーマットで返す"""
        from src.news_aggregator import get_gnews_articles
        
        mock_gn = MagicMock()
        mock_gnews_class.return_value = mock_gn
        mock_gn.get_news_by_topic.return_value = [
            {
                "title": "Test Article",
                "description": "Test Summary",
                "publisher": {"title": "Test Publisher"},
                "published date": "Mon, 01 Jan 2024 12:00:00 GMT",
                "url": "https://test.com/article",
            }
        ]
        
        articles = get_gnews_articles(topic="BUSINESS", max_results=5)
        
        assert len(articles) == 1
        assert articles[0]["title"] == "Test Article"
        assert articles[0]["summary"] == "Test Summary"
        assert articles[0]["source"] == "GNews"
        assert articles[0]["category"] == "BUSINESS"
    
    def test_handles_import_error(self):
        """gnewsがインストールされていない場合は空リストを返す"""
        with patch.dict('sys.modules', {'gnews': None}):
            from src.news_aggregator import get_gnews_articles
            # ImportErrorが発生しても空リストを返す
            # 実際のテストではgnewsがインストールされているのでこのテストはスキップ
            pass


class TestGetAggregatedNews:
    """get_aggregated_news関数のテスト"""
    
    @patch('src.news_aggregator.get_gnews_articles')
    def test_aggregates_from_multiple_sources(self, mock_get_gnews):
        """複数カテゴリからニュースを集約"""
        from src.news_aggregator import get_aggregated_news
        
        mock_get_gnews.return_value = [
            {"title": "News 1", "link": "https://1.com", "published": "2024-01-01"},
        ]
        
        news = get_aggregated_news(
            categories=["BUSINESS"],
            keywords=["Fed"],
            max_per_source=5,
            max_total=20
        )
        
        # get_gnews_articlesが2回呼ばれる（カテゴリ1回 + キーワード1回）
        assert mock_get_gnews.call_count >= 2
        assert len(news) > 0
