"""Shared, model-free daily research workspace for CLI and the local launcher."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from src.research import runner
from src.research.bundle import new_bundle, validate_bundle
from src.research.comparison import fetch_comparisons
from src.research.policy import synthesize
from src.research.render import render_dashboard, save_bundle
from src.storage.atomic_json import read_json, write_json

RESERVED = {
    "market",
    "markets",
    "theme",
    "themes",
    "policy",
    "policies",
    "comparisons",
    "diagnostics",
}


def read_snapshot(path: Path) -> dict:
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Snapshot too large")
    return validate_bundle(json.loads(path.read_text(encoding="utf-8")))


def saved_workspace(root: Path) -> dict:
    """Recover saved work without a provider request; prefer the atomic pointer."""
    runs = (root / ".states" / "research_runs").resolve()
    pointer = root / ".states" / "research_workbench" / "current.json"
    preferred = None
    try:
        directory = read_json(pointer, {}).get("directory", "")
        if (
            directory
            and Path(directory).name == directory
            and (runs / directory).resolve().is_relative_to(runs)
        ):
            preferred = read_snapshot(runs / directory / "research.json")
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    snapshots = []
    for path in [*runs.glob("*/research.json"), *runs.glob("*/attached_*.json")]:
        try:
            snapshots.append(read_snapshot(path))
        except (OSError, ValueError, TypeError, KeyError):
            continue  # One malformed historical file must not break the launcher.
    snapshots.sort(key=lambda b: b["created_at"])
    sections: dict = {"markets": {}, "themes": {}, "policies": {}, "comparisons": {}}
    origins = {}
    interpretations = {}
    legacy_rankings = {}
    for bundle in snapshots:
        for record in bundle.get("saved_interpretations", []):
            interpretations[record["run_id"]] = deepcopy(record)
        if bundle.get("interpretations"):
            interpretations[bundle["run_id"]] = {
                "run_id": bundle["run_id"],
                "created_at": bundle["created_at"],
                "interpretations": deepcopy(bundle["interpretations"]),
                "inputs": {
                    "evidence": {
                        "sources": deepcopy(
                            bundle["inputs"].get("evidence", {}).get("sources", [])
                        )
                    }
                },
            }
        market = bundle["inputs"]["market"]
        market_packets = dict(bundle["sections"].get("markets", {}))
        if bundle["sections"].get("market"):
            market_packets[market] = bundle["sections"]["market"]
        for selected_market, packet in market_packets.items():
            ranking = packet.get("analysis", {}).get("trend_ranking", {})
            if ranking.get("items") and ranking.get("profile") != "standard":
                legacy_rankings[selected_market] = {
                    "ranking": deepcopy(ranking),
                    "run_id": bundle["run_id"],
                    "snapshot_created_at": bundle["created_at"],
                    "status": "legacy_research_only",
                }
        if preferred is None:
            for key in ("markets", "themes", "policies", "comparisons"):
                sections[key].update(bundle["sections"].get(key, {}))
            for singular in ("market", "theme", "policy"):
                if singular in bundle["sections"]:
                    plural = "policies" if singular == "policy" else singular + "s"
                    sections[plural][market] = bundle["sections"][singular]
        for ticker, packet in bundle["sections"].items():
            if ticker not in RESERVED:
                origin = bundle.get("saved_stock_origins", {}).get(
                    ticker,
                    {"run_id": bundle["run_id"], "created_at": bundle["created_at"]},
                )
                if (
                    ticker in origins
                    and origin["created_at"] < origins[ticker]["created_at"]
                ):
                    continue
                sections[ticker] = deepcopy(packet)
                sections[ticker]["market"] = "JP" if ticker.endswith(".T") else market
                origins[ticker] = origin
    # Keep the newest saved interpretation per scope, with its original sources.
    latest_scopes = {}
    records = sorted(
        interpretations.values(), key=lambda record: record.get("created_at", "")
    )
    for record in records:
        for item in record["interpretations"]:
            latest_scopes[item["scope"]] = record["run_id"]
    kept_interpretations = []
    for record in records:
        items = [
            item
            for item in record["interpretations"]
            if latest_scopes[item["scope"]] == record["run_id"]
        ]
        if items:
            kept_interpretations.append({**record, "interpretations": items})
    if preferred is not None:
        preferred = deepcopy(preferred)
        preferred["sections"].update(
            {key: packet for key, packet in sections.items() if key not in RESERVED}
        )
        preferred["saved_stock_origins"] = origins
        preferred["saved_interpretations"] = kept_interpretations
        for selected_market, record in legacy_rankings.items():
            analysis = (
                preferred["sections"]
                .get("markets", {})
                .get(selected_market, {})
                .get("analysis")
            )
            if analysis is not None and analysis.get("profile") == "standard":
                analysis["legacy_trend_ranking"] = record
        return preferred
    result = new_bundle("update", {"market": "US", "scope": "saved"}, sections)
    result["saved_stock_origins"] = origins
    result["saved_interpretations"] = kept_interpretations
    result["warnings"].append(
        "保存結果の集約。データ取得・一次資料の再確認は行っていません。"
    )
    return result


@contextmanager
def update_lock(path: Path):
    """Nonblocking cross-process OS lock, automatically released after a crash."""
    import os

    with path.open("a+b") as file:
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                file.write(b"0")
                file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def retain_on_failure(previous: dict, attempted: dict, label: str) -> tuple[dict, bool]:
    """Keep old observations and the failed attempt separate, never silently fresh."""
    failed = bool(
        attempted.get("error_type")
        or attempted.get("analysis", {}).get("errors")
        or attempted.get("status") in {"unavailable", "failed"}
    )
    if not failed:
        return attempted, False
    packet = deepcopy(previous or attempted)
    packet["refresh_failure"] = {
        "stage": label,
        "status": "partial" if previous else "unavailable",
        "previous_result_retained": bool(previous),
        "warning": "今回の取得に失敗。以前の値は最新値ではありません。",
    }
    packet["attempted_analysis"] = attempted
    return packet, True


def update_research(
    previous: dict,
    scope: str = "all",
    progress: Callable[[str], None] = lambda _: None,
    profile: str = "standard",
    market_inputs: dict | None = None,
) -> dict:
    if profile not in {"standard", "advanced"}:
        raise ValueError("Unsupported profile")
    if scope not in {"all", "US", "JP"}:
        raise ValueError("Unsupported scope")
    validate_bundle(previous)
    selected = ("US", "JP") if scope == "all" else (scope,)
    if profile == "standard":
        return update_standard(previous, selected, scope, progress, market_inputs)
    if market_inputs is not None:
        raise ValueError("Reviewed market inputs require standard profile")
    sections = deepcopy(previous["sections"])
    for name in ("markets", "themes", "policies", "comparisons"):
        sections.setdefault(name, {})
    partial = False
    for market in selected:
        name = "米国" if market == "US" else "日本"
        progress(f"{name}：市場・信用・ボラ・センチメントを更新中")
        packet = runner.capture(lambda market=market: runner.market(market, False))
        sections["markets"][market], failed = retain_on_failure(
            sections["markets"].get(market, {}), packet, "market"
        )
        partial |= failed
        partial |= any(
            row.get("status") in {"partial", "unavailable", "error", "failed", "stale"}
            or row.get("is_partial")
            or row.get("is_stale")
            or row.get("error")
            for row in packet.get("analysis", {}).get("data_status", [])
        )
        progress(f"{name}：テーマ・構成銘柄・候補を更新中（個別深掘りなし）")
        packet = runner.capture(lambda market=market: runner.theme(market))
        sections["themes"][market], failed = retain_on_failure(
            sections["themes"].get(market, {}), packet, "theme"
        )
        partial |= failed
        partial |= bool(packet.get("ranking", {}).get("quality_warnings"))
        leaders = packet.get("leaders", {})
        partial |= bool(
            leaders.get("is_partial") or leaders.get("is_stale") or leaders.get("error")
        )
    progress("指数比較を更新中")
    comparisons = runner.capture(lambda: fetch_comparisons(selected))
    for market in selected:
        attempted = comparisons.get(market, comparisons)
        old = sections["comparisons"].get(market, {})
        if attempted.get("error_type"):
            sections["comparisons"][market], _ = retain_on_failure(
                old, attempted, "comparisons"
            )
            partial = True
        else:
            series = []
            for i, item in enumerate(attempted.get("series", [])):
                previous_series = old.get("series", [])
                retained, failed = retain_on_failure(
                    previous_series[i] if i < len(previous_series) else {},
                    item,
                    "index",
                )
                # A caught provider failure can be a status without an exception.
                if not item.get("points"):
                    partial = True
                series.append(retained)
                partial |= failed
            sections["comparisons"][market] = {**attempted, "series": series}
    progress("方針・取得状態を整理して保存中")
    for market in selected:
        inputs = {
            "market": sections["markets"][market],
            "theme": sections["themes"][market],
        }
        policy = synthesize(inputs, market)
        policy["missing"].append(
            "個別銘柄の深掘り・一次資料再確認は今回の一括更新対象外。必要な銘柄を指定してください。"
        )
        policy["input_scope"] = "market and theme only; no individual-stock refresh"
        sections["policies"][market] = policy
    sections["diagnostics"] = runner.capture(runner.diagnostics)
    result = new_bundle(
        "update",
        {
            "market": selected[0],
            "scope": scope,
            "profile": profile,
            "allow_options": False,
            "scan_fomo": False,
        },
        sections,
    )
    result["execution_status"] = "partial" if partial else "completed"
    result["saved_stock_origins"] = deepcopy(previous.get("saved_stock_origins", {}))
    result["saved_interpretations"] = deepcopy(
        previous.get("saved_interpretations", [])
    )
    result["updated_from"] = {
        "run_id": previous["run_id"],
        "created_at": previous["created_at"],
    }
    result["warnings"].append(
        "一括更新は市場・テーマ・候補・方針・取得状態。保存済み個別株・会計・評価・Codex解釈は元の基準日のままです。"
    )
    return validate_bundle(result)


def update_standard(
    previous: dict,
    selected: tuple[str, ...],
    scope: str,
    progress,
    market_inputs: dict | None = None,
) -> dict:
    from src.research.standard import standard_sections

    sections = deepcopy(previous["sections"])
    retained_inputs = (
        market_inputs
        if market_inputs is not None
        else previous["inputs"].get("market_inputs")
    )
    if retained_inputs is not None:
        from src.research.public_sources import validate_market_inputs

        validate_market_inputs(retained_inputs)
    attempted = runner.capture(
        lambda: standard_sections(
            selected,
            progress=progress,
            **(
                {"market_inputs": retained_inputs}
                if retained_inputs is not None
                else {}
            ),
        )
    )
    partial = bool(attempted.get("error_type"))
    for name in ("markets", "themes", "comparisons", "policies"):
        sections.setdefault(name, {})
        for market in selected:
            old = sections[name].get(market, {})
            new = attempted.get(name, {}).get(market, attempted if partial else {})
            if name == "markets" and new.get("analysis"):
                analysis = new["analysis"]
                unavailable = all(
                    r["quality"] == "unavailable"
                    for r in analysis["connected"]["observations"]
                    if r["id"].startswith("index:")
                )
                if unavailable:
                    new["status"] = "unavailable"
                else:
                    old_analysis = deepcopy(old.get("analysis", {}))
                    states = {
                        key: old_analysis.get("field_updates", {}).get(key)
                        or {
                            "status": "not_updated",
                            "original_snapshot_created_at": previous["created_at"],
                            "observed_on": value.get("observed_on")
                            or value.get("as_of")
                            if isinstance(value, dict)
                            else None,
                        }
                        for key, value in old_analysis.items()
                        if key not in analysis and key != "field_updates"
                    }
                    analysis = {**old_analysis, **analysis, "field_updates": states}
                    new = {**new, "analysis": analysis}
                    partial |= any(
                        r.get("quality") != "available"
                        for r in analysis["connected"]["observations"]
                    )
                    partial |= any(
                        r.get("status") != "available"
                        for r in analysis["connected"]["event_sources"]
                    )
            if (
                name == "themes"
                and new.get("ranking")
                and not any(r.get("rank") is not None for r in new["ranking"]["items"])
            ):
                new["status"] = (
                    "partial"
                    if any(
                        r.get("performance_6m") is not None
                        for r in new["ranking"]["items"]
                    )
                    else "unavailable"
                )
            retained, failed = retain_on_failure(old, new, name)
            sections[name][market] = retained
            partial |= failed
    if not attempted.get("error_type"):
        sections["diagnostics"] = attempted["diagnostics"]
    for market in selected:
        connected = sections["markets"][market].get("analysis", {}).get("connected")
        if connected:
            sections["policies"][market] = {
                "status": "research_only",
                "market": market,
                "connected": deepcopy(connected),
                "input_scope": "same saved market observations; no independent recalculation",
            }
    result = new_bundle(
        "update",
        {
            "market": selected[0],
            "scope": scope,
            "profile": "standard",
            "allow_options": False,
            "scan_fomo": False,
            **(
                {"market_inputs": deepcopy(retained_inputs)}
                if retained_inputs is not None
                else {}
            ),
        },
        sections,
    )
    result["execution_status"] = "partial" if partial else "completed"
    result["saved_stock_origins"] = deepcopy(previous.get("saved_stock_origins", {}))
    result["saved_interpretations"] = deepcopy(
        previous.get("saved_interpretations", [])
    )
    result["updated_from"] = {
        "run_id": previous["run_id"],
        "created_at": previous["created_at"],
    }
    result["warnings"].append(
        "標準更新。旧独自分析は今回の対象外、元の値と日付を保持。個別株・会計・評価・資料確認日は更新していません。"
    )
    return validate_bundle(result)


class Workbench:
    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.Lock()
        self.bundle = saved_workspace(root)
        self.html = render_dashboard(self.bundle, embedded=True)
        self.status = {
            "running": False,
            "message": "保存結果を表示しています。更新はボタンを押したときだけです。",
            "revision": 0,
            "result": "saved",
        }

    def snapshot_status(self) -> dict:
        with self.lock:
            return deepcopy(self.status)

    def dashboard(self, reload_saved: bool = False) -> str:
        if reload_saved and not self.snapshot_status()["running"]:
            bundle = saved_workspace(self.root)
            html = render_dashboard(bundle, embedded=True)
            with self.lock:
                if not self.status["running"]:
                    self.bundle, self.html = bundle, html
        with self.lock:
            return self.html

    def begin(
        self, scope: str, profile: str = "standard", mode: str = "prices"
    ) -> bool:
        if profile not in {"standard", "advanced"}:
            raise ValueError("Unsupported profile")
        if scope not in {"all", "US", "JP"}:
            raise ValueError("Unsupported scope")
        if (
            mode not in {"prices", "fundamentals", "all"}
            or mode != "prices"
            and profile != "standard"
        ):
            raise ValueError("Unsupported update mode")
        with self.lock:
            if self.status["running"]:
                return False
            self.status.update(
                running=True, message="更新を開始しています。", result="running"
            )
        threading.Thread(
            target=self.update,
            args=(scope, profile),
            kwargs={"mode": mode} if mode != "prices" else {},
            daemon=True,
        ).start()
        return True

    def update(
        self,
        scope: str = "all",
        profile: str = "standard",
        market_inputs: dict | None = None,
        mode: str = "prices",
    ) -> Path | None:
        def progress(message: str) -> None:
            with self.lock:
                self.status["message"] = message

        # A crashed process releases this OS lock. CLI and portal cannot overlap.
        directory = self.root / ".states" / "research_workbench"
        try:
            if (
                mode not in {"prices", "fundamentals", "all"}
                or mode != "prices"
                and profile != "standard"
            ):
                raise ValueError("Unsupported update mode")
            directory.mkdir(parents=True, exist_ok=True)
            with update_lock(directory / "update.lock"):
                previous = saved_workspace(self.root)
                updated = (
                    deepcopy(previous)
                    if mode == "fundamentals"
                    else update_research(
                        previous,
                        scope,
                        progress,
                        profile=profile,
                        **(
                            {"market_inputs": market_inputs}
                            if market_inputs is not None
                            else {}
                        ),
                    )
                )
                if mode in {"fundamentals", "all"}:
                    from src.research.fundamentals import refresh_fundamentals

                    selected = ("US", "JP") if scope == "all" else (scope,)
                    if not any(
                        updated["sections"]
                        .get("markets", {})
                        .get(m, {})
                        .get("analysis", {})
                        .get("topdown", {})
                        .get("screening")
                        for m in selected
                    ):
                        raise ValueError(
                            "Update market prices before financial screening"
                        )
                    if mode == "fundamentals":
                        updated = new_bundle(
                            "screen",
                            {**previous["inputs"], "scope": scope},
                            deepcopy(previous["sections"]),
                        ) | {
                            k: deepcopy(previous[k])
                            for k in ("saved_stock_origins", "saved_interpretations")
                            if k in previous
                        }
                        updated["updated_from"] = {
                            "run_id": previous["run_id"],
                            "created_at": previous["created_at"],
                        }
                    report = refresh_fundamentals(
                        updated, selected, progress, root=self.root
                    )
                    updated["sections"].setdefault("diagnostics", {})[
                        "fundamentals_update"
                    ] = report
                    if report["status"] == "partial":
                        updated["execution_status"] = "partial"
                updated["inputs"]["update_mode"] = mode
                output = save_bundle(
                    updated, self.root / ".states" / "research_runs" / str(uuid4())
                )
                html = render_dashboard(updated, embedded=True)
                write_json(directory / "current.json", {"directory": output.name})
                with self.lock:
                    self.bundle, self.html = updated, html
                    self.status.update(
                        result=updated["execution_status"],
                        revision=self.status["revision"] + 1,
                        message=(
                            "一部取得できませんでした。前回値・欠損を明示して表示しています。"
                            if updated["execution_status"] == "partial"
                            else "更新結果を表示しました。各データの観測日も確認してください。"
                        ),
                        output=str(output),
                    )
                return output
        except Exception as exc:
            # Never expose credential-bearing exception strings over localhost.
            with self.lock:
                self.status.update(
                    result="failed",
                    message=f"更新できませんでした（{type(exc).__name__}）。以前の表示を維持しています。別の更新実行中なら完了後に再試行してください。",
                )
            return None
        finally:
            with self.lock:
                self.status["running"] = False
