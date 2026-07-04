import pandas as pd

from src.services.vix_sq_alert_service import build_vix_sq_alert_context


def test_vix_sq_alert_flags_uptrend_during_sq_week():
    dates = pd.bdate_range("2026-04-01", periods=80)
    vix = pd.Series([15 + i * 0.18 for i in range(80)], index=dates)
    cboe = pd.DataFrame({"VIX": vix}, index=dates)

    context = build_vix_sq_alert_context(cboe, today="2026-07-15")

    assert context["status"] == "hedge_alert"
    assert context["in_sq_week"] is True
    assert context["monthly_expiration"] == "2026-07-17"


def test_vix_sq_alert_reports_unavailable_without_vix_history():
    context = build_vix_sq_alert_context(pd.DataFrame({"VVIX": [100.0]}))

    assert context["status"] == "unavailable"
    assert context["quality_warnings"]
