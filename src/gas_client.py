"""
GAS (Google Apps Script) クライアントモジュール
スプレッドシートをバックエンドとしてポートフォリオを管理します。
履歴保存・アラート通知機能を含む。
"""

from dataclasses import dataclass
from typing import Literal, Optional

import requests


@dataclass
class GasConfig:
    """GAS設定"""

    script_url: str
    timeout: int = 30


AlertType = Literal["daily_change", "value_below", "value_above"]


class GasClient:
    """
    Google Apps Script Web App クライアント

    使用例:
        client = GasClient("https://script.google.com/macros/s/xxx/exec")
        client.save_portfolio("マイポートフォリオ", [...])
    """

    def __init__(self, script_url: str, timeout: int = 30):
        """
        Args:
            script_url: GASのWeb App URL
            timeout: リクエストタイムアウト秒数
        """
        self.url = script_url.rstrip("/")
        self.timeout = timeout

    def _get(self, params: dict) -> dict:
        """GETリクエスト"""
        try:
            resp = requests.get(self.url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    def _post(self, data: dict) -> dict:
        """POSTリクエスト"""
        try:
            resp = requests.post(self.url, json=data, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    # ============================================================
    # ポートフォリオ管理
    # ============================================================

    def list_portfolios(self) -> list[str]:
        """
        保存済みポートフォリオ一覧を取得

        Returns:
            ポートフォリオ名のリスト
        """
        result = self._get({"action": "list"})
        return result.get("portfolios", [])

    def load_portfolio(self, name: str) -> Optional[dict]:
        """
        ポートフォリオを読み込み

        Args:
            name: ポートフォリオ名

        Returns:
            ポートフォリオデータ、またはエラー時None
        """
        result = self._get({"action": "load", "name": name})
        if "error" in result:
            return None
        return result

    def save_portfolio(self, name: str, holdings: list[dict]) -> bool:
        """
        ポートフォリオを保存

        Args:
            name: ポートフォリオ名
            holdings: 保有銘柄リスト [{"ticker": "AAPL", "shares": 10, "avg_cost": 150.0}, ...]

        Returns:
            保存成功時True
        """
        result = self._post({"action": "save", "name": name, "holdings": holdings})
        return result.get("success", False)

    def delete_portfolio(self, name: str) -> bool:
        """
        ポートフォリオを削除

        Args:
            name: ポートフォリオ名

        Returns:
            削除成功時True
        """
        result = self._post({"action": "delete", "name": name})
        return result.get("success", False)

    # ============================================================
    # 履歴管理
    # ============================================================

    def save_snapshot(
        self, name: str, total_value: float, holdings: list[dict]
    ) -> bool:
        """
        ポートフォリオのスナップショットを保存

        Args:
            name: ポートフォリオ名
            total_value: 総資産額
            holdings: 保有銘柄リスト

        Returns:
            保存成功時True
        """
        result = self._post(
            {
                "action": "save_snapshot",
                "name": name,
                "total_value": total_value,
                "holdings": holdings,
            }
        )
        return result.get("success", False)

    def get_history(self, name: str, days: int = 30) -> list[dict]:
        """
        ポートフォリオの履歴を取得

        Args:
            name: ポートフォリオ名
            days: 取得日数

        Returns:
            履歴リスト
        """
        result = self._get({"action": "history", "name": name, "days": str(days)})
        return result.get("history", [])

    # ============================================================
    # アラート管理
    # ============================================================

    def set_alert(
        self, portfolio_name: str, email: str, alert_type: AlertType, threshold: float
    ) -> bool:
        """
        アラートを設定

        Args:
            portfolio_name: ポートフォリオ名
            email: 通知先メールアドレス
            alert_type: アラートタイプ
                - "daily_change": 日次変動率が閾値を超えた場合
                - "value_below": 評価額が閾値を下回った場合
                - "value_above": 評価額が閾値を超えた場合
            threshold: 閾値（変動率の場合は%、評価額の場合はドル）

        Returns:
            設定成功時True
        """
        result = self._post(
            {
                "action": "set_alert",
                "portfolio_name": portfolio_name,
                "email": email,
                "alert_type": alert_type,
                "threshold": threshold,
            }
        )
        return result.get("success", False)

    def delete_alert(self, portfolio_name: str, alert_type: AlertType) -> bool:
        """
        アラートを削除

        Args:
            portfolio_name: ポートフォリオ名
            alert_type: アラートタイプ

        Returns:
            削除成功時True
        """
        result = self._post(
            {
                "action": "delete_alert",
                "portfolio_name": portfolio_name,
                "alert_type": alert_type,
            }
        )
        return result.get("success", False)

    def get_alerts(self, portfolio_name: Optional[str] = None) -> list[dict]:
        """
        アラート一覧を取得

        Args:
            portfolio_name: ポートフォリオ名（省略時は全件）

        Returns:
            アラートリスト
        """
        params = {"action": "alerts"}
        if portfolio_name:
            params["name"] = portfolio_name
        result = self._get(params)
        return result.get("alerts", [])

    def send_alert_email(self, email: str, subject: str, body: str) -> bool:
        """
        アラートメールを直接送信

        Args:
            email: 送信先メールアドレス
            subject: 件名
            body: 本文

        Returns:
            送信成功時True
        """
        result = self._post(
            {"action": "send_alert", "email": email, "subject": subject, "body": body}
        )
        return result.get("success", False)

    # ============================================================
    # 参照知識管理 (Knowledge Base)
    # ============================================================

    def save_knowledge_item(self, item: dict) -> bool:
        """
        参照知識を保存

        Args:
            item: KnowledgeItemの辞書表現

        Returns:
            保存成功時True
        """
        result = self._post({"action": "save_knowledge", "item": item})
        return result.get("success", False)

    def get_all_knowledge(self) -> list[dict]:
        """
        全参照知識を取得

        Returns:
            参照知識リスト
        """
        result = self._get({"action": "get_knowledge"})
        return result.get("items", [])

    def delete_knowledge_item(self, item_id: str) -> bool:
        """
        参照知識を削除

        Args:
            item_id: 削除するアイテムID

        Returns:
            削除成功時True
        """
        result = self._post({"action": "delete_knowledge", "id": item_id})
        return result.get("success", False)


# シングルトンインスタンス（設定後に使用）
_gas_client: Optional[GasClient] = None


def configure_gas(script_url: str, timeout: int = 30) -> GasClient:
    """
    GASクライアントを設定

    Args:
        script_url: GASのWeb App URL
        timeout: タイムアウト秒数

    Returns:
        設定されたGasClientインスタンス
    """
    global _gas_client
    _gas_client = GasClient(script_url, timeout)
    return _gas_client


def get_gas_client() -> Optional[GasClient]:
    """設定済みのGASクライアントを取得"""
    return _gas_client
