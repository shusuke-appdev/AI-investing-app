from src.services.stock_trade_analysis_service import build_stock_trade_analysis


def test_stock_trade_analysis_uses_existing_dashboard_payload():
    result = build_stock_trade_analysis(
        {
            "ticker": "NVDA",
            "technical_data": {
                "overall_score": 72,
                "support_price": 880.0,
                "resistance_price": 940.0,
                "stop_loss": 850.0,
                "ma_50": 890.0,
                "ma_200": 720.0,
                "atr_percent": 3.2,
                "obv_trend": "上昇",
                "stage_data": {
                    "stage": 2,
                    "description": "ステージ2 (上昇局面)",
                    "current_price": 920.0,
                },
                "vcp_data": {
                    "is_vcp": True,
                    "breakout_price": 945.0,
                    "contractions": 3,
                },
            },
            "trade_setup": {
                "status": "ready",
                "summary": "日足Entryトリガー成立。",
                "current_price": 920.0,
                "ma50": 890.0,
                "ma200": 720.0,
                "breakout_price": 945.0,
                "atr_percent": 3.2,
                "rvol_display": "1.80x",
                "checks": [
                    {
                        "label": "RVOL",
                        "status": "pass",
                        "value_display": "1.80x",
                        "rationale": "出来高確認。",
                    }
                ],
            },
            "sector_theme_context": {
                "combined_rating": "high",
                "ranking_summary": "AI半導体は首位。",
                "stock_flow_score_display": "+45.0",
                "theme_option_signal": "upside_squeeze_candidate",
            },
            "fomo_regime": {"risk_level": "normal", "label": "通常"},
            "trend_follow_diagnostics": {"summary": "上昇トレンドは堅調。"},
            "probabilistic_signal": {"label": "上昇優位", "probability": 0.62},
            "purchase_evidence": {
                "status": "available",
                "label": "高",
                "score_display": "82/100",
                "summary": "高 82点。",
            },
            "purchase_evidence_health": [
                {
                    "feature": "theme_rank",
                    "label": "テーマ順位",
                    "status_key": "ok",
                    "status_label": "OK",
                    "value": "10pt -> 100/100",
                    "detail": "AI半導体は首位。",
                    "effect": "ファンダメンタル・テーマ側の30%。",
                    "required": True,
                }
            ],
        }
    )

    assert result["ticker"] == "NVDA"
    assert result["stance_key"] == "ready"
    assert result["stance_label"] == "仕掛け候補"
    assert any(item["label"] == "ブレイク水準" for item in result["key_levels"])
    assert any(item["label"] == "Minerviniステージ" for item in result["timing_checks"])
    assert any(item["label"] == "テーマフロー" for item in result["supply_demand"])
    assert result["risk"]["final_stop"] == "850.00"
    assert result["purchase_evidence"]["score_display"] == "82/100"
    assert result["purchase_evidence_health"][0]["feature"] == "theme_rank"


def test_stock_trade_analysis_blocks_stage4_even_when_setup_waits():
    result = build_stock_trade_analysis(
        {
            "ticker": "TEST",
            "technical_data": {
                "overall_score": 45,
                "support_price": 90.0,
                "stage_data": {"stage": 4, "description": "ステージ4 (下落局面)"},
            },
            "trade_setup": {"status": "wait", "summary": "監視継続。"},
        }
    )

    assert result["stance_key"] == "protect"
    assert "見送り" in result["timing"]["primary"]
