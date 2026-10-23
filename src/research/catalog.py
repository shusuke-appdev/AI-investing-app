"""Feature-to-screen contract, shared by rendering and parity acceptance."""

MARKET_FEATURES = {
    "market_data": "基本市況・指数・金利・セクター・商品・為替",
    "market_charts": "保存された市場価格履歴",
    "evaluation": "市場環境評価",
    "ibd_regime": "IBD式市場状態（代理）",
    "regime_playbook": "市場状態別の研究課題",
    "microstructure": "市場構造・流動性（代理）",
    "momentum": "期間別テーマモメンタム",
    "monitor": "売り抜け・過熱・利回り監視",
    "market_distortions": "市場歪み・乖離",
    "trend_ranking": "総合テーマ順位",
    "opportunity_themes": "相対優位テーマ候補",
    "important_levels": "支持抵抗・価格帯別出来高",
    "market_timeframes": "時間軸別見通し",
    "strategy_regime": "戦略レジーム（研究姿勢）",
    "market_driver_monitor": "金利・商品・為替ドライバー",
    "japan_conditions": "日本市場の条件別確認",
    "sector_flow": "セクター・テーマ資金注目度（代理）",
    "credit_stress": "信用ストレス",
    "flow_monitor": "ETFリーダーシップ（代理）",
    "flow_alignment": "市場・テーマ整合性",
    "cross_market": "市場間比較",
    "volatility_regime": "ボラティリティ・レジーム",
    "vix_sq_alert": "VIX・SQ週の警戒条件",
    "sentiment": "センチメント",
    "short_horizon_forecast": "短期予測・検証状態",
    "composite_sentiment": "複合センチメント",
    "top_risk_signposts": "リスク兆候",
    "fomo_scan": "過熱候補スキャン",
    "options": "オプション（明示許可時のみ）",
}

STOCK_FEATURES = {
    "info": "企業概要・企業指標",
    "news": "ニュース・公表日時",
    "technical_data": "テクニカル・支持抵抗",
    "smart_criteria": "成長株SMART条件（参考）",
    "probabilistic_signal": "類似局面・確率・配分（参考）",
    "trend_follow_diagnostics": "Trend Follow過去検証（参考）",
    "fomo_regime": "過熱・急変リスク（参考）",
    "trade_setup": "Entry・無効化条件",
    "sector_theme_context": "所属セクター・テーマ",
    "fundamental_profile": "業種別ファンダメンタル",
    "volume_profile": "価格帯別出来高（代理）",
    "purchase_evidence": "根拠一致度（参考）",
    "purchase_evidence_health": "根拠一致度の入力状態",
    "market_risk_guardrail": "市場ガードレール（参考のみ）",
    "japan_supply_demand": "日本株の需給期日",
    "primary_conditions": "Stage 2・RS・VCP・出来高・成長・Entry",
    "stock_signal_context": "表示とCodexの共有入力",
}

OPERATIONS = {
    "market_summary": (
        "市場",
        "market --refresh <research.json> --stage summary",
        "test_refresh_summary_preserves_unrelated",
    ),
    "market_detail_stages": (
        "市場",
        "market --refresh <research.json> --stage theme-flow|credit-risk|vol-sentiment",
        "test_refresh_failure_retains_previous",
    ),
    "market_options": (
        "市場",
        "market --refresh <research.json> --stage options --allow-options",
        "test_refresh_options_scope",
    ),
    "stock_chart": ("銘柄", "stock --ticker <ticker>", "stock_chart_browser"),
    "theme_filters": ("テーマ", "theme --market US|JP", "theme_controls_browser"),
    "candidate_deep_dive": (
        "テーマ",
        "theme --resume <research.json> --evidence <reviewed.json>",
        "test_interpretation_preserves_analysis",
    ),
    "multiple_valuation": (
        "銘柄",
        "stock --resume <research.json> --evidence <reviewed.json>",
        "test_multiple_valuations_v2",
    ),
    "saved_file_import": (
        "データ状況",
        "overview --replay <research.json> --attach <other.json>",
        "atomic_import_browser",
    ),
}


def coverage_state(value) -> str:
    if value is None or value == "" or value == {} or value == []:
        return "unavailable"
    if isinstance(value, dict):
        if value.get("error_type"):
            return "unavailable"
        if value.get("status") in {
            "unavailable",
            "partial",
            "research_only",
            "insufficient_data",
        }:
            return value["status"]
    return "captured"


def feature_coverage(bundle: dict) -> list[dict]:
    rows = []
    sections = bundle["sections"]
    packets = sections.get("markets") or {
        bundle["inputs"].get("market", "US"): sections.get("market", {})
    }
    for market, packet in packets.items():
        analysis = packet.get("analysis", {})
        for field, label in MARKET_FEATURES.items():
            value = analysis.get(field)
            rows.append(
                {
                    "scope": market,
                    "feature": label,
                    "path": f"markets.{market}.analysis.{field}"
                    if "markets" in sections
                    else f"market.analysis.{field}",
                    "screen": "市場",
                    "state": coverage_state(value),
                }
            )
    for ticker, packet in sections.items():
        if ticker in {
            "market",
            "markets",
            "theme",
            "themes",
            "policy",
            "comparisons",
            "diagnostics",
        }:
            continue
        analysis = packet.get("analysis", {})
        for field, label in STOCK_FEATURES.items():
            rows.append(
                {
                    "scope": ticker,
                    "feature": label,
                    "path": f"{ticker}.analysis.{field}",
                    "screen": "銘柄",
                    "state": coverage_state(analysis.get(field)),
                }
            )
    return rows
