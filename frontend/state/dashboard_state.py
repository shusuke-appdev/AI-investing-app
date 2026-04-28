import reflex as rx
import os
import asyncio
import httpx
from typing import List, Dict, Any

class DashboardState(rx.State):
    """メインのダッシュボード用ステート管理クラス"""
    
    # リアクティブ変数
    ticker: str = "AAPL"
    chart_data: List[Dict[str, Any]] = []
    is_fetching: bool = False
    error_msg: str = ""

    def set_ticker(self, value: str):
        self.ticker = value


    async def fetch_financial_data(self):
        """外部APIから金融データを非同期で取得する"""
        if not self.ticker:
            self.error_msg = "ティッカーシンボルを入力してください。"
            return
            
        self.is_fetching = True
        self.error_msg = ""
        yield  # UIにローディング状態を反映させる
        
        # 実際の外部APIキーは os.getenv() を通して安全に取得
        # api_key = os.getenv("FINANCIAL_API_KEY")
        
        try:
            # 実際のAPIリクエストのシミュレーション（非同期）
            # 本番環境では httpx や aiohttp を使用して外部APIにアクセスします
            await asyncio.sleep(1.5)  # ネットワーク通信の遅延をシミュレート
            
            # モックデータ生成（実際はJSONレスポンスをパースする）
            # Rechartsで利用しやすい形式
            import random
            base_price = 150.0 if self.ticker.upper() == "AAPL" else 100.0
            
            new_chart_data = []
            current_price = base_price
            for i in range(30):
                change = random.uniform(-2, 2.5)
                current_price += change
                new_chart_data.append({
                    "name": f"Day {i+1}",
                    "price": round(current_price, 2),
                })
            
            self.chart_data = new_chart_data
            
        except Exception as e:
            self.error_msg = f"データの取得に失敗しました: {str(e)}"
            self.chart_data = []
        finally:
            self.is_fetching = False
            yield  # 完了をUIに反映
