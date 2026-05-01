import reflex as rx
import asyncio
from typing import Dict, Any, List
from pydantic import BaseModel

class MarketSignal(BaseModel):
    name: str = ""
    score: float = 0.0
    weight: float = 0.0
    rationale: str = ""

class OptionSummary(BaseModel):
    ticker: str = ""
    sentiment: str = "中立"
    current_price: float = 0.0
    pcr_vol: float = 0.0
    pcr_vol_str: str = ""
    net_gex: float = 0.0
    net_gex_str: str = ""
    iv: str = "-"
    max_pain: str = "-"
    analysis: List[str] = []

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
    market_signals: List[MarketSignal] = []
    
    # オプション分析データ
    option_analysis: List[OptionSummary] = []
    
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
            from src.option_analyst import get_major_indices_options
            
            # 同期ブロッキング関数をバックグラウンドスレッドで実行
            raw_data_task = asyncio.to_thread(get_market_indices, self.market_type)
            option_data_task = asyncio.to_thread(get_major_indices_options, self.market_type)
            config_task = asyncio.to_thread(get_market_config, self.market_type)
            
            raw_data, option_data, config = await asyncio.gather(raw_data_task, option_data_task, config_task)
            
            # Format option data for UI
            opt_list = []
            if option_data:
                for opt in option_data:
                    iv_val = opt.get("iv")
                    mp_val = opt.get("max_pain")
                    pcr_dict = opt.get("pcr") or {}
                    gex_dict = opt.get("gex") or {}
                    pcr_val = float(pcr_dict.get("volume_pcr", 0.0))
                    gex_val = float(gex_dict.get("nearby_net_gex", 0.0))
                    opt_list.append(OptionSummary(
                        ticker=opt.get("ticker", ""),
                        sentiment=opt.get("sentiment", "中立"),
                        current_price=opt.get("current_price", 0.0),
                        pcr_vol=pcr_val,
                        pcr_vol_str=f"{pcr_val:.2f}",
                        net_gex=gex_val,
                        net_gex_str=f"{gex_val / 1e6:+.0f}M",
                        iv=f"{iv_val*100:.1f}%" if iv_val is not None else "-",
                        max_pain=f"${mp_val:.0f}" if mp_val is not None else "-",
                        analysis=opt.get("analysis", [])
                    ))
            
            self.option_analysis = opt_list
            eval_data = await asyncio.to_thread(evaluate_market_environment, self.market_type, option_data)
            
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
                        change_rounded = round(float(d.get('change', 0.0)), 1)
                        indices_list.append({"name": name, "price": f"¥{d.get('price', 0):,.0f}", "change": change_rounded})
            
            for name, data in raw_data.items():
                if name in ("trend_1mo", "weekly_performance"):
                    continue
                ticker = data.get("ticker", "")
                price = data.get("price", 0.0)
                change = data.get("change", 0.0)
                change_rounded = round(float(change), 1)
                
                item = {"name": name, "change": change_rounded}
                
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
            
            # 型推論可能なリストとしてシグナルを抽出
            if "signals" in eval_data:
                self.market_signals = [
                    MarketSignal(
                        name=s.get("name", ""),
                        score=float(s.get("score", 0.0)),
                        weight=float(s.get("weight", 0.0)),
                        rationale=s.get("rationale", "")
                    ) for s in eval_data["signals"]
                ]
            else:
                self.market_signals = []
                
        except Exception as e:
            self.error_msg = f"データの取得に失敗しました: {str(e)}"
            self.indices_data = []
            self.sectors_data = []
            self.others_data = []
            self.option_analysis = []
            self.market_signals = []
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
