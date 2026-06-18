from src import momentum_monitor


def test_momentum_context_preserves_distinct_leaders_and_laggards(monkeypatch):
    ranked = [
        {"theme": f"Theme {index}", "performance": float(10 - index)}
        for index in range(10)
    ]
    monkeypatch.setattr(
        momentum_monitor,
        "get_ranked_theme_periods",
        lambda periods, market: {period: ranked for period in periods},
    )

    result = momentum_monitor.get_momentum_themes.__wrapped__("US", top_n=3)

    themes = result["超短期 (1W)"]
    assert [item["theme"] for item in themes[:3]] == [
        "Theme 0",
        "Theme 1",
        "Theme 2",
    ]
    assert [item["theme"] for item in themes[-3:]] == [
        "Theme 7",
        "Theme 8",
        "Theme 9",
    ]
