import reflex as rx
import asyncio
from typing import Dict, Any, List

class MarketState(rx.State):
    """マーケット（市況）ページ用の状態管理クラス"""
    
    market_type: str = "US"
    is_fetching: bool = False
    error_msg: str = ""
    
    # UI表示用の整形済みデータリスト
    indices_data: List[Dict[str, Any]] = []
    sectors_data: List[Dict[str, Any]] = []
    others_data: List[Dict[str, Any]] = []
    
    # 市場環境の評価結果
    evaluation: Dict[str, Any] = {}
    
    # AIレポート関連
    ai_recap: str = ""
    is_generating_recap: bool = False

    def set_market_type(self, m_type: str):
        """対象市場の切り替え（US / JP）"""
        self.market_type = m_type
        # 切り替えたら即座に再取得
        return MarketState.fetch_market_data

    async def fetch_market_data(self):
        """外部APIから市場データを取得する"""
        self.is_fetching = True
        self.error_msg = ""
        yield
            
        try:
            from src.market_data import get_market_indices
            from src.advisor.market_environment import evaluate_market_environment
            from src.market_config import get_market_config
            
            # 同期ブロッキング関数をバックグラウンドスレッドで実行
            raw_data = await asyncio.to_thread(get_market_indices, self.market_type)
            eval_data = await asyncio.to_thread(evaluate_market_environment, self.market_type, None)
            config = await asyncio.to_thread(get_market_config, self.market_type)
            
            # データをカテゴライズしてリスト化
            indices_list = []
            sectors_list = []
            others_list = []
            
            idx_tickers = set(config["indices"].values())
            sec_tickers = set(config.get("sectors", {}).values())
            other_tickers = set(config.get("commodities", {}).values()) | set(config.get("crypto", {}).values()) | set(config.get("forex", {}).values()) | set(config.get("treasuries", {}).values())
            
            # 日本市場の特別対応
            if self.market_type == "JP":
                jp_names = ["日経平均", "TOPIX"]
                for name in jp_names:
                    if name in raw_data:
                        d = raw_data[name]
                        indices_list.append({"name": name, "price": f"¥{d.get('price', 0):,.0f}", "change": d.get('change', 0.0)})
            
            for name, data in raw_data.items():
                if name in ("trend_1mo", "weekly_performance"):
                    continue
                ticker = data.get("ticker", "")
                price = data.get("price", 0.0)
                change = data.get("change", 0.0)
                
                item = {"name": name, "change": change}
                
                if ticker in idx_tickers and self.market_type != "JP":
                    item["price"] = f"{price:,.0f}"
                    indices_list.append(item)
                elif ticker in sec_tickers:
                    item["price"] = f"${price:.2f}"
                    sectors_list.append(item)
                elif ticker in other_tickers:
                    if "JPY" in name:
                        item["price"] = f"¥{price:.2f}"
                    elif "BTC" in ticker or "ETH" in ticker:
                        item["price"] = f"${price / 1000:.1f}K"
                    elif "GC" in ticker or "Gold" in name or "Silver" in name:
                        item["price"] = f"${price:,.2f}" if "Silver" in name else f"${price:,.0f}"
                    else:
                        item["price"] = f"${price:.2f}"
                    if ticker in set(config.get("treasuries", {}).values()):
                        item["price"] = f"{price:.2f}%"
                    others_list.append(item)
            
            self.indices_data = indices_list
            self.sectors_data = sectors_list
            self.others_data = others_list
            self.evaluation = eval_data
                
        except Exception as e:
            self.error_msg = f"データの取得に失敗しました: {str(e)}"
            self.indices_data = []
            self.sectors_data = []
            self.others_data = []
        finally:
            self.is_fetching = False
            yield

    async def generate_ai_recap(self):
        """GeminiによるAI市況レポート生成"""
        self.is_generating_recap = True
        yield
            
        try:
            from src.services.market_analyst_service import generate_market_analysis_report
            
            # APIコールのブロッキングを回避
            recap = await asyncio.to_thread(generate_market_analysis_report, self.market_type)
            
            if recap:
                self.ai_recap = recap
            else:
                self.error_msg = "レポートの生成に失敗しました。"
        except Exception as e:
            self.error_msg = f"AI Recap 生成エラー: {e}"
        finally:
            self.is_generating_recap = False
            yield
