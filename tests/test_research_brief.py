"""Chat delivery preserves observation periods and cannot trigger an update."""

import importlib.util
import json
from pathlib import Path

import pytest

from src.research.brief import render_brief
from src.research.bundle import new_bundle


def brief_bundle():
    data = {
        "benchmark_status": "available",
        "indices": [
            {
                "name": "Test index",
                "observed_on": "2024-01-01",
                "label": "上昇基調",
                "short_term": "20日線下",
                "ma_gaps": {"200": 0, "20": -2.5},
            }
        ],
        "breadth": {
            "registered_count": 3,
            "scope": "登録標本",
            "latest": {
                "date": "2024-01-01",
                "above_200": 0,
                "counts": {"above_200": {"numerator": 0, "denominator": 3}},
            },
        },
        "sectors": [],
        "summary": [],
    }
    items = [
        {"theme": "negative", "relative_6m": -5, "performance_6m": 8},
        {"theme": "zero", "relative_6m": 0, "performance_6m": 4},
        {"theme": "missing", "relative_6m": None, "performance_6m": None},
    ]
    return new_bundle(
        "update",
        {"market": "US"},
        {
            "markets": {"US": {"analysis": {"topdown": data}}},
            "themes": {"US": {"ranking": {"items": items}}},
        },
    )


def test_brief_preserves_zero_negative_unknown_and_observation_date():
    result = render_brief(brief_bundle(), ("US",))
    assert "2024-01-01" in result and "20日線下" in result
    assert "+0.0%" in result and "-2.5%" in result and "未確認" in result
    assert result.index("| zero |") < result.index("| negative |")
    assert "| missing |" not in result
    assert "全市場の統計ではありません" in result


def test_unavailable_relative_benchmark_is_not_replaced_by_absolute_rank():
    bundle = brief_bundle()
    bundle["sections"]["markets"]["US"]["analysis"]["topdown"]["benchmark_status"] = (
        "unavailable"
    )
    result = render_brief(bundle, ("US",))
    assert "相対順位の代替ではありません" in result
    assert "6か月絶対騰落" in result
    assert result.index("| negative |") < result.index("| zero |")
    assert "+0.0pp" not in result


def test_saved_cli_reads_only_and_does_not_open_or_update(
    monkeypatch, tmp_path, capsys
):
    spec = importlib.util.spec_from_file_location(
        "research_cli_for_brief", Path("scripts/research.py").resolve()
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    bundle = new_bundle("update", {"market": "US"}, {})
    directory = tmp_path / ".states/research_runs/original"
    directory.mkdir(parents=True)
    original = json.dumps(bundle).encode()
    (directory / "research.json").write_bytes(original)
    from src.research import runner, workbench

    def unexpected(*args, **kwargs):
        pytest.fail("Saved reading cannot acquire, update or launch a browser")

    monkeypatch.setattr(runner, "run", unexpected)
    monkeypatch.setattr(workbench.Workbench, "update", unexpected)
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", unexpected)
    monkeypatch.setattr("sys.argv", ["research.py", "saved", "--scope", "JP"])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "## 日本" in output and "## 米国" not in output
    assert "保存入力がありません" in output
    assert (directory / "research.json").read_bytes() == original
    assert not (tmp_path / ".states/research_workbench").exists()
    monkeypatch.setattr("sys.argv", ["research.py", "saved", "--refresh-fundamentals"])
    with pytest.raises(SystemExit):
        cli.main()
