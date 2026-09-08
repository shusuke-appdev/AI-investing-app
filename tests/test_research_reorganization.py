import ast
import copy
from pathlib import Path

import numpy as np
import pandas as pd

from src.services.stock_primary_conditions import build_primary_conditions
from src.services.stock_trade_analysis_service import build_stock_trade_analysis


def prices(sessions=260):
    close = np.linspace(50, 100, sessions)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(sessions, 1_000_000),
        },
        index=pd.bdate_range("2025-01-01", periods=sessions),
    )


def test_primary_conditions_keep_missing_growth_and_history_unknown():
    result = build_primary_conditions(
        prices(30), prices(30), {"revenue_growth": float("nan")}, {}
    )
    conditions = {item["label"]: item for item in result["conditions"]}
    for label in (
        "Stage 2",
        "VCP",
        "市場に対する相対強度",
        "売上成長率",
        "利益成長率",
        "日足Entry条件",
    ):
        assert conditions[label]["status"] == "unknown"
    assert result["stop_reference"] == "判定不能"
    assert "score" not in result


def test_primary_conditions_use_shared_stage_and_volume_evidence():
    from src.advisor.minervini_analyzer import analyze_stage
    from src.advisor.price_action_metrics import volume_contraction

    frame = prices()
    result = build_primary_conditions(
        frame, frame, {"revenue_growth": 0.25, "earnings_growth": -0.1}, {}
    )
    rows = {row["label"]: row for row in result["conditions"]}
    for condition in analyze_stage(frame)["conditions"]:
        assert rows[condition["label"]]["status"] == condition["status"]
    assert rows["出来高収縮"]["status"] == (
        "pass" if volume_contraction(frame.Volume) else "fail"
    )
    assert rows["売上成長率"]["value"] == "25.00%"
    assert rows["利益成長率"]["status"] == "fail"
    assert rows["ピボットとの距離"]["status"] == "reference"


def test_market_risk_is_display_only_for_stock_timing():
    context = {
        "ticker": "TEST",
        "technical_data": {"overall_score": 85},
        "trade_setup": {"status": "ready", "current_price": 100, "atr": 2},
    }
    before = build_stock_trade_analysis(context)
    guarded = copy.deepcopy(context)
    guarded["market_risk_guardrail"] = {
        "status": "active",
        "action_cap": "protect",
        "risk_level": "extreme",
        "summary": "market reference only",
    }
    after = build_stock_trade_analysis(guarded)
    assert before["stance_key"] == after["stance_key"]


def test_stock_ai_does_not_receive_market_option_context(monkeypatch):
    from src import stock_analyst

    prompts = []
    monkeypatch.setattr(
        stock_analyst,
        "generate_content",
        lambda prompt, **kwargs: prompts.append(prompt) or "ok",
    )
    result = stock_analyst.analyze_stock(
        "TEST",
        {},
        stock_signal_context={
            "primary_conditions": {
                "conditions": [{"label": "Stage 2", "status": "unknown"}]
            },
            "technical_data": {"overall_score": 50},
            "smart_criteria": {"S": {"status": "unknown"}},
            "market_risk_guardrail": {"summary": "FORBIDDEN_MARKET_PAYLOAD"},
            "sector_theme_context": {
                "theme_option_summary": "FORBIDDEN_MARKET_PAYLOAD"
            },
            "data_status": [
                {"name": "market_risk_guardrail", "error": "FORBIDDEN_MARKET_PAYLOAD"}
            ],
        },
    )
    assert result == "ok"
    assert "FORBIDDEN_MARKET_PAYLOAD" not in prompts[0]
    assert "【主条件】" in prompts[0]
    assert "Stage 2" in prompts[0]
    assert "参考分析" in prompts[0]


def test_active_application_has_no_personal_storage_or_single_stock_option_imports():
    retired = {
        "src.supabase_client",
        "src.knowledge_storage",
        "src.portfolio_storage",
        "src.trading_plan_storage",
        "src.knowledge_extractor",
        "supabase",
    }
    for root in (Path("src"), Path("frontend")):
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom):
                    assert node.module not in retired, path
                elif isinstance(node, ast.Import):
                    assert not retired.intersection(item.name for item in node.names), (
                        path
                    )
    technical = Path("src/advisor/technical.py").read_text(encoding="utf-8")
    assert "analyze_options_data" not in technical
    for filename in (
        "requirements.txt",
        "requirements-lock.txt",
        "requirements-dev-lock.txt",
    ):
        assert "supabase==" not in Path(filename).read_text(encoding="utf-8")


def test_hosted_import_needs_no_storage_backend(monkeypatch):
    from src.deployment_guard import require_safe_deployment
    from src.settings_storage import get_gemini_api_key

    monkeypatch.setenv("SPACE_ID", "owner/research")
    monkeypatch.setenv("PRIVATE_DEPLOYMENT_ACK", "1")
    for name in ("APP_STORAGE_BACKEND", "SUPABASE_URL", "SUPABASE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    require_safe_deployment()
    assert isinstance(get_gemini_api_key(), str)
