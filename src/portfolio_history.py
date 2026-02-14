"""
ポートフォリオ履歴管理モジュール
資産推移の記録・取得を行います。
"""
import json
from pathlib import Path
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, asdict
from src.log_config import get_logger

logger = get_logger(__name__)


HISTORY_DIR = Path(__file__).parent.parent / "data" / "portfolio_history"


@dataclass
class PortfolioSnapshot:
    """ポートフォリオのスナップショット"""
    date: str  # YYYY-MM-DD
    portfolio_name: str
    total_value: float
    holdings: list[dict]  # [{"ticker": "AAPL", "shares": 10, "value": 1500}, ...]


def ensure_history_dir():
    """履歴ディレクトリを作成"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def get_history_file(portfolio_name: str) -> Path:
    """履歴ファイルパスを取得"""
    return HISTORY_DIR / f"{portfolio_name}_history.json"


def save_snapshot(portfolio_name: str, total_value: float, holdings: list[dict]) -> bool:
    """
    ポートフォリオのスナップショットを保存します。
    同じ日付のデータは上書きされます。
    
    Args:
        portfolio_name: ポートフォリオ名
        total_value: 総資産額
        holdings: 保有銘柄リスト
    
    Returns:
        保存成功時True
    """
    ensure_history_dir()
    
    today = date.today().isoformat()
    
    snapshot = {
        "date": today,
        "portfolio_name": portfolio_name,
        "total_value": total_value,
        "holdings": [
            {
                "ticker": h.get("ticker"),
                "shares": h.get("shares"),
                "value": h.get("value", 0),
                "weight": h.get("weight", 0),
            }
            for h in holdings
        ]
    }
    
    # 既存履歴を読み込み
    history = load_history(portfolio_name)
    
    # 同じ日付があれば更新、なければ追加
    updated = False
    for i, h in enumerate(history):
        if h.get("date") == today:
            history[i] = snapshot
            updated = True
            break
    
    if not updated:
        history.append(snapshot)
    
    # 日付でソート
    history.sort(key=lambda x: x.get("date", ""))
    
    # 保存
    try:
        with open(get_history_file(portfolio_name), "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving history: {e}")
        return False


def load_history(portfolio_name: str, days: Optional[int] = None) -> list[dict]:
    """
    ポートフォリオの履歴を読み込みます。
    
    Args:
        portfolio_name: ポートフォリオ名
        days: 取得する日数（省略時は全件）
    
    Returns:
        スナップショットのリスト
    """
    history_file = get_history_file(portfolio_name)
    
    if not history_file.exists():
        return []
    
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        if days:
            return history[-days:]
        return history
    except Exception as e:
        logger.error(f"Error loading history: {e}")
        return []


def get_value_series(portfolio_name: str, days: int = 30) -> tuple[list[str], list[float]]:
    """
    資産推移のデータ系列を取得します。
    
    Args:
        portfolio_name: ポートフォリオ名
        days: 取得日数
    
    Returns:
        (日付リスト, 資産額リスト)
    """
    history = load_history(portfolio_name, days)
    
    dates = [h.get("date", "") for h in history]
    values = [h.get("total_value", 0) for h in history]
    
    return dates, values


def calculate_returns(portfolio_name: str, days: int = 30) -> dict:
    """
    リターンを計算します。
    
    Args:
        portfolio_name: ポートフォリオ名
        days: 計算期間
    
    Returns:
        リターン情報
    """
    history = load_history(portfolio_name, days)
    
    if len(history) < 2:
        return {"period_return": None, "daily_returns": []}
    
    start_value = history[0].get("total_value", 0)
    end_value = history[-1].get("total_value", 0)
    
    if start_value == 0:
        return {"period_return": None, "daily_returns": []}
    
    period_return = ((end_value - start_value) / start_value) * 100
    
    # 日次リターン
    daily_returns = []
    for i in range(1, len(history)):
        prev = history[i-1].get("total_value", 0)
        curr = history[i].get("total_value", 0)
        if prev > 0:
            daily_returns.append({
                "date": history[i].get("date"),
                "return": ((curr - prev) / prev) * 100
            })
    
    return {
        "period_return": period_return,
        "daily_returns": daily_returns,
        "start_value": start_value,
        "end_value": end_value,
        "days": len(history),
    }


def list_portfolios_with_history() -> list[str]:
    """
    履歴があるポートフォリオ一覧を取得します。
    
    Returns:
        ポートフォリオ名のリスト
    """
    ensure_history_dir()
    
    portfolios = []
    for f in HISTORY_DIR.glob("*_history.json"):
        name = f.stem.replace("_history", "")
        portfolios.append(name)
    
    return sorted(portfolios)


def compare_portfolios(names: list[str], days: int = 30) -> dict:
    """
    複数ポートフォリオを比較します。
    
    Args:
        names: ポートフォリオ名のリスト
        days: 比較期間
    
    Returns:
        比較データ
    """
    result = {
        "portfolios": [],
        "dates": set(),
    }
    
    for name in names:
        history = load_history(name, days)
        returns = calculate_returns(name, days)
        
        dates, values = get_value_series(name, days)
        result["dates"].update(dates)
        
        # 正規化（開始時点を100として）
        if values and values[0] > 0:
            normalized = [(v / values[0]) * 100 for v in values]
        else:
            normalized = values
        
        result["portfolios"].append({
            "name": name,
            "dates": dates,
            "values": values,
            "normalized": normalized,
            "period_return": returns.get("period_return"),
            "current_value": values[-1] if values else 0,
        })
    
    result["dates"] = sorted(result["dates"])
    
    return result
