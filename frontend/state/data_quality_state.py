import os

import reflex as rx
from pydantic import BaseModel


class ProviderStatus(BaseModel):
    name: str = ""
    status: str = ""
    detail: str = ""


class DataQualityState(rx.State):
    """Non-secret provider configuration summary for the data-quality page."""

    refresh_key: int = 0

    def refresh_provider_statuses(self):
        self.refresh_key += 1

    @rx.var
    def provider_statuses(self) -> list[ProviderStatus]:
        _ = self.refresh_key
        return _provider_statuses()


def _provider_statuses() -> list[ProviderStatus]:
    from src.finnhub_client import is_configured as finnhub_is_configured
    from src.marketdata_client import is_configured as marketdata_is_configured
    from src.option_data_provider import marketdata_options_status

    marketdata = marketdata_options_status()
    return [
        ProviderStatus(
            name="MarketData.app",
            status="configured" if marketdata_is_configured() else "not_configured",
            detail=(
                "token=設定済み / "
                f"mode={marketdata['effective_mode']} / "
                f"allowed={len(marketdata['allowed_tickers'])} tickers"
                if marketdata_is_configured()
                else "token未設定。米国オプションはyfinance/cache fallbackで継続します。"
            ),
        ),
        ProviderStatus(
            name="Finnhub",
            status="configured" if finnhub_is_configured() else "not_configured",
            detail="企業ニュース・決算補完に使用します。"
            if finnhub_is_configured()
            else "未設定。ニュース・決算補完は利用不可または縮退します。",
        ),
        ProviderStatus(
            name="FRED",
            status="best_effort",
            detail="公開CSVとstale cacheで信用ストレスを取得します。",
        ),
        ProviderStatus(
            name="J-Quants",
            status="configured"
            if _env_configured("JQUANTS_API_KEY")
            else "optional_missing",
            detail="日本株企業マスター・財務補完用。価格の現在値経路には使いません。",
        ),
        ProviderStatus(
            name="EDINET",
            status="configured"
            if _env_configured("EDINET_API_KEY")
            else "optional_missing",
            detail="日本株財務補完用。",
        ),
        ProviderStatus(
            name="Supabase",
            status="configured"
            if _env_configured("SUPABASE_URL")
            else "optional_missing",
            detail="個人データの任意同期先。未設定時はローカルJSONを使います。",
        ),
        ProviderStatus(
            name="yfinance",
            status="best_effort",
            detail="株価・履歴・fallback optionの主経路。レート制限時はrepo-local cacheを使用します。",
        ),
    ]


def _env_configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())
