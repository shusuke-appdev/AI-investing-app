"""Theme metadata used by ranking, sector flow, and option proxy analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.themes_config import get_themes


@dataclass(frozen=True)
class ThemeProfile:
    """Stable metadata for one configured sector or theme."""

    theme: str
    market_type: str = "US"
    parent_sector: str = ""
    proxy_ticker: str = ""
    option_proxy_ticker: str = ""
    representative_tickers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["representative_tickers"] = list(self.representative_tickers)
        return value


US_THEME_PROFILES: dict[str, tuple[str, str, str]] = {
    # Technology / AI
    "AI半導体": ("情報技術", "SMH", "SMH"),
    "半導体": ("情報技術", "SOXX", "SOXX"),
    "半導体指数": ("情報技術", "SOXX", "SOXX"),
    "半導体製造装置": ("情報技術", "SOXX", "SOXX"),
    "AIインフラ/データセンター": ("情報技術", "SRVR", "SMH"),
    "AI利活用/ソフトウェア": ("情報技術", "IGV", "IGV"),
    "AIエージェント": ("情報技術", "IGV", "IGV"),
    "生成AI": ("情報技術", "QQQ", "QQQ"),
    "クラウド": ("情報技術", "WCLD", "IGV"),
    "サイバーセキュリティ": ("情報技術", "CIBR", "CIBR"),
    "量子コンピュータ": ("情報技術", "QTUM", "QQQ"),
    "フィンテック": ("金融", "FINX", "FINX"),
    "ブロックチェーン/暗号資産": ("金融", "BLOK", "BLOK"),
    "仮想通貨関連": ("金融", "BLOK", "BLOK"),
    # Financials
    "メガバンク": ("金融", "KBE", "KBE"),
    "地銀/リージョナルバンク": ("金融", "KRE", "KRE"),
    "保険": ("金融", "KIE", "KIE"),
    "資産運用": ("金融", "XLF", "XLF"),
    "決済/ペイメント": ("金融", "IPAY", "IPAY"),
    "ネオバンク/デジタル銀行": ("金融", "FINX", "FINX"),
    # Health care
    "バイオテック": ("ヘルスケア", "XBI", "XBI"),
    "医薬品大手": ("ヘルスケア", "XPH", "XLV"),
    "医療機器": ("ヘルスケア", "IHI", "IHI"),
    "遺伝子治療/CRISPR": ("ヘルスケア", "ARKG", "ARKG"),
    "肥満治療薬 (GLP-1)": ("ヘルスケア", "XLV", "XLV"),
    "ヘルステック": ("ヘルスケア", "XLV", "XLV"),
    # Industrials / infrastructure
    "防衛": ("資本財", "ITA", "ITA"),
    "宇宙/衛星": ("資本財", "ARKX", "ARKX"),
    "ドローン/eVTOL": ("資本財", "ARKX", "ARKX"),
    "ロボティクス/自動化": ("資本財", "BOTZ", "BOTZ"),
    "産業オートメーション": ("資本財", "XLI", "XLI"),
    "電力インフラ": ("資本財", "PAVE", "PAVE"),
    "変圧器/送電/グリッド": ("資本財", "GRID", "GRID"),
    "5G/通信インフラ": ("通信", "XLC", "XLC"),
    # Energy / materials
    "石油・ガス": ("エネルギー", "XLE", "XLE"),
    "LNG": ("エネルギー", "XLE", "XLE"),
    "原子力/SMR": ("エネルギー", "URA", "URA"),
    "ウラン": ("エネルギー", "URA", "URA"),
    "太陽光": ("エネルギー", "TAN", "TAN"),
    "風力/再エネ": ("公益", "ICLN", "ICLN"),
    "水素/燃料電池": ("エネルギー", "ICLN", "ICLN"),
    "エネルギー貯蔵/蓄電池": ("資本財", "LIT", "LIT"),
    "リチウム": ("素材", "LIT", "LIT"),
    "銅": ("素材", "COPX", "COPX"),
    "金・貴金属": ("素材", "GDX", "GDX"),
    "銀": ("素材", "SLV", "SLV"),
    "レアアース/戦略金属": ("素材", "REMX", "REMX"),
    # Consumer / media / real estate
    "Eコマース": ("一般消費財", "IBUY", "IBUY"),
    "ストリーミング": ("通信", "XLC", "XLC"),
    "ゲーム/Eスポーツ": ("通信", "HERO", "HERO"),
    "スポーツベッティング": ("一般消費財", "BETZ", "BETZ"),
    "飲食/QSR": ("一般消費財", "XLY", "XLY"),
    "REIT（商業）": ("不動産", "XLRE", "XLRE"),
    "REIT（物流/データセンター）": ("不動産", "VPN", "XLRE"),
    "データセンターREIT": ("不動産", "VPN", "XLRE"),
    "電力/ユーティリティ": ("公益", "XLU", "XLU"),
}


SECTOR_ETF_PROFILES: dict[str, tuple[str, str, str]] = {
    "情報技術": ("情報技術", "XLK", "XLK"),
    "ヘルスケア": ("ヘルスケア", "XLV", "XLV"),
    "金融": ("金融", "XLF", "XLF"),
    "一般消費財": ("一般消費財", "XLY", "XLY"),
    "通信": ("通信", "XLC", "XLC"),
    "資本財": ("資本財", "XLI", "XLI"),
    "生活必需品": ("生活必需品", "XLP", "XLP"),
    "エネルギー": ("エネルギー", "XLE", "XLE"),
    "公益": ("公益", "XLU", "XLU"),
    "不動産": ("不動産", "XLRE", "XLRE"),
    "素材": ("素材", "XLB", "XLB"),
}


def get_theme_profile(
    theme: str,
    market_type: str = "US",
    *,
    tickers: list[str] | None = None,
) -> ThemeProfile:
    """Return metadata for a theme, using ETFs where a liquid proxy exists."""

    members = tuple((tickers or get_themes(market_type).get(theme, []))[:5])
    if market_type == "JP":
        return ThemeProfile(
            theme=theme,
            market_type="JP",
            parent_sector=_infer_jp_parent_sector(theme),
            proxy_ticker="",
            option_proxy_ticker="",
            representative_tickers=members,
        )

    parent, proxy, option_proxy = (
        US_THEME_PROFILES.get(theme)
        or SECTOR_ETF_PROFILES.get(theme)
        or (_infer_us_parent_sector(theme), "", "")
    )
    return ThemeProfile(
        theme=theme,
        market_type="US",
        parent_sector=parent,
        proxy_ticker=proxy,
        option_proxy_ticker=option_proxy or proxy,
        representative_tickers=members,
    )


def get_market_theme_profiles(market_type: str = "US") -> dict[str, ThemeProfile]:
    """Return metadata for all configured themes in one market."""

    return {
        theme: get_theme_profile(theme, market_type, tickers=tickers)
        for theme, tickers in get_themes(market_type).items()
    }


def marketdata_option_universe() -> set[str]:
    """Tickers where the app may explicitly request MarketData.app options."""

    tickers = {"SPY", "QQQ", "IWM"}
    for _, proxy, option_proxy in US_THEME_PROFILES.values():
        if proxy:
            tickers.add(proxy.upper())
        if option_proxy:
            tickers.add(option_proxy.upper())
    for _, proxy, option_proxy in SECTOR_ETF_PROFILES.values():
        if proxy:
            tickers.add(proxy.upper())
        if option_proxy:
            tickers.add(option_proxy.upper())
    return tickers


def _infer_us_parent_sector(theme: str) -> str:
    if any(word in theme for word in ("AI", "半導体", "クラウド", "ソフト", "量子")):
        return "情報技術"
    if any(word in theme for word in ("銀行", "金融", "決済", "資産", "暗号")):
        return "金融"
    if any(word in theme for word in ("医", "薬", "バイオ", "ヘルス")):
        return "ヘルスケア"
    if any(word in theme for word in ("石油", "ガス", "ウラン", "電力", "水素")):
        return "エネルギー"
    if any(word in theme for word in ("金", "銀", "銅", "リチウム", "素材")):
        return "素材"
    if any(word in theme for word in ("REIT", "不動産")):
        return "不動産"
    if any(word in theme for word in ("防衛", "宇宙", "ロボ", "産業", "インフラ")):
        return "資本財"
    if any(word in theme for word in ("通信", "ゲーム", "メディア")):
        return "通信"
    return "その他"


def _infer_jp_parent_sector(theme: str) -> str:
    if any(word in theme for word in ("半導体", "電子", "IT", "ゲーム", "ソフト")):
        return "テクノロジー"
    if any(word in theme for word in ("自動車", "機械", "ロボ", "建設")):
        return "製造・資本財"
    if any(word in theme for word in ("銀行", "保険", "証券", "リース")):
        return "金融"
    if any(word in theme for word in ("医薬", "医療", "CRO")):
        return "ヘルスケア"
    return "日本テーマ"
