import os

import reflex as rx
from pydantic import BaseModel


class ProviderStatus(BaseModel):
    name: str = ""
    status: str = ""
    mode: str = ""
    message: str = ""
    detail: str = ""


class ProviderHealthDisplay(BaseModel):
    name: str = ""
    status_key: str = "unavailable"
    status_label: str = "未取得"
    source: str = ""
    scope: str = ""
    last_success_at: str = ""
    last_error_at: str = ""
    last_error: str = ""
    cache_status: str = ""
    cache_age_label: str = ""
    degraded_reason: str = ""


class DataQualityState(rx.State):
    """Non-secret provider configuration summary for the data-quality page."""

    refresh_key: int = 0

    def refresh_provider_statuses(self):
        self.refresh_key += 1

    @rx.var
    def provider_statuses(self) -> list[ProviderStatus]:
        _ = self.refresh_key
        return _provider_statuses()

    @rx.var
    def provider_health(self) -> list[ProviderHealthDisplay]:
        _ = self.refresh_key
        return _provider_health()


def _provider_statuses() -> list[ProviderStatus]:
    from src.app_mode import app_capability_summary
    from src.finnhub_client import is_configured as finnhub_is_configured
    from src.marketdata_client import is_configured as marketdata_is_configured
    from src.option_data_provider import marketdata_options_status

    marketdata = marketdata_options_status()
    capabilities = app_capability_summary()
    return [
        ProviderStatus(
            name="アプリ実行モード",
            status=(
                "configured" if capabilities["mode"] == "private" else "best_effort"
            ),
            mode=str(capabilities["mode"]),
            message=str(capabilities["mode"]),
            detail=(
                "private: 個人データ・AI生成・外部コンテンツ取得が有効です。"
                if capabilities["mode"] == "private"
                else "public_readonly: 個人データ・AI生成・外部コンテンツ取得を拒否します。"
            )
            + (
                " APP_MODEで明示設定されています。"
                if capabilities["explicitly_configured"]
                else " APP_MODE未設定のため安全側の既定値を使用しています。"
            ),
        ),
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
        _supabase_provider_status(),
        ProviderStatus(
            name="yfinance",
            status="best_effort",
            detail="株価・履歴・fallback optionの主経路。レート制限時はrepo-local cacheを使用します。",
        ),
    ]


def _env_configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _supabase_provider_status() -> ProviderStatus:
    has_url = _env_configured("SUPABASE_URL")
    key_mode = _supabase_key_mode()
    if not has_url:
        return ProviderStatus(
            name="Supabase",
            status="optional_missing",
            mode="missing_url",
            message="SUPABASE_URL未設定",
            detail="SUPABASE_URL未設定。個人データはローカルJSON保存になります。",
        )
    if key_mode == "missing_key":
        return ProviderStatus(
            name="Supabase",
            status="not_configured",
            mode="missing_key",
            message="Supabase key未設定",
            detail=(
                "SUPABASE_URLはありますが、SUPABASE_SECRET_KEY / "
                "SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY が未設定です。"
            ),
        )
    if key_mode == "configured_secret":
        return ProviderStatus(
            name="Supabase",
            status="configured",
            mode=key_mode,
            message="secret key設定済み",
            detail="SUPABASE_URLとSUPABASE_SECRET_KEYを使って個人データを同期できます。",
        )
    return ProviderStatus(
        name="Supabase",
        status="configured",
        mode=key_mode,
        message="legacy key設定済み",
        detail=(
            "SUPABASE_URLと互換キーを検出しました。新規環境では "
            "SUPABASE_SECRET_KEY を推奨します。"
        ),
    )


def _supabase_key_mode() -> str:
    if _env_configured("SUPABASE_SECRET_KEY"):
        return "configured_secret"
    if _env_configured("SUPABASE_SERVICE_ROLE_KEY") or _env_configured("SUPABASE_KEY"):
        return "configured_legacy"
    return "missing_key"


def _provider_health() -> list[ProviderHealthDisplay]:
    from src.services.provider_health import load_provider_health

    rows = []
    for item in load_provider_health():
        payload = item.to_dict()
        rows.append(
            ProviderHealthDisplay(
                name=str(payload.get("name") or ""),
                status_key=str(payload.get("status_key") or "unavailable"),
                status_label=str(payload.get("status_label") or "未取得"),
                source=str(payload.get("source") or ""),
                scope=str(payload.get("scope") or ""),
                last_success_at=str(payload.get("last_success_at") or ""),
                last_error_at=str(payload.get("last_error_at") or ""),
                last_error=str(payload.get("last_error") or ""),
                cache_status=str(payload.get("cache_status") or ""),
                cache_age_label=_cache_age_label(payload.get("cache_age_seconds")),
                degraded_reason=str(payload.get("degraded_reason") or ""),
            )
        )
    return rows


def _cache_age_label(value) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return ""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"
