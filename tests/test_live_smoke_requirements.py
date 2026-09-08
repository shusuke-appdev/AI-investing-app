from argparse import Namespace

from scripts.live_smoke import Check, _failed_checks, _required_check_names


def _args(**overrides) -> Namespace:
    values = {
        "require_finnhub": False,
        "require_edinet": False,
        "require_marketdata": False,
        "require_market_forecast": False,
        "require_yfinance_options": False,
    }
    values.update(overrides)
    return Namespace(**values)


def test_explicit_flags_map_to_their_own_checks():
    required = _required_check_names(
        _args(
            require_finnhub=True,
            require_edinet=True,
            require_marketdata=True,
            require_market_forecast=True,
            require_yfinance_options=True,
        )
    )

    assert required == {
        "finnhub",
        "edinet",
        "marketdata_options",
        "market_forecast",
        "yfinance_options",
    }


def test_unrelated_skips_do_not_fail_required_finnhub():
    checks = [
        Check("finnhub", "PASS", "ok"),
        Check("market_forecast", "SKIP", "not requested"),
        Check("edinet", "SKIP", "not configured"),
    ]

    assert _failed_checks(checks, {"finnhub"}) == []


def test_required_degraded_or_skipped_check_fails_once():
    checks = [
        Check("marketdata_options", "DEGRADED", "partial"),
        Check("finnhub", "SKIP", "not configured"),
        Check("external_market", "FAIL", "offline"),
    ]

    failures = _failed_checks(checks, {"marketdata_options", "finnhub"})

    assert {failure.name for failure in failures} == {
        "marketdata_options",
        "finnhub",
        "external_market",
    }
