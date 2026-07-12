"""Execution, cache, normalization, and status helpers for market orchestration."""

# ruff: noqa: F403, F405

from src.services import market_dashboard_service as _service
from src.services.market_dashboard_service import *
from src.services.market_dashboard_service import _MARKET_STAGE_EXECUTORS


def _sync_compat_dependencies() -> None:
    """Honor dependency patches applied to the historical facade."""

    for name in tuple(globals()):
        if not name.startswith("__") and hasattr(_service, name):
            globals()[name] = getattr(_service, name)


def _build_option_context(market_type: str) -> OptionContext:
    _sync_compat_dependencies()
    try:
        result = get_major_indices_option_status(market_type)
        failed_tickers = list(result.get("failed_tickers") or [])
        status = str(result.get("status") or "unavailable")
        return OptionContext(
            items=list(result.get("items") or []),
            error_message=str(result.get("error_message") or ""),
            status=status,
            failed_tickers=failed_tickers,
            source=str(result.get("source") or "yfinance"),
            fetched_at=str(result.get("fetched_at") or ""),
            is_stale=bool(result.get("is_stale", False)),
            is_partial=status == "partial" or bool(failed_tickers),
            quality_warnings=list(result.get("quality_warnings") or []),
            cache_status=str(result.get("cache_status") or "live"),
            cache_age_seconds=_optional_float(result.get("cache_age_seconds")),
            data_as_of=str(result.get("data_as_of") or ""),
            data_mode=str(result.get("data_mode") or ""),
            resolved_expiration=str(result.get("resolved_expiration") or ""),
            resolved_dte=_optional_int(result.get("resolved_dte")),
            expiration_policy=str(result.get("expiration_policy") or ""),
            expiration_fallback_reason=str(
                result.get("expiration_fallback_reason") or ""
            ),
            credits_consumed=_optional_int(result.get("credits_consumed")),
            credits_remaining=_optional_int(result.get("credits_remaining")),
            provider_active=bool(result.get("provider_active", False)),
            fallback_reason=str(result.get("fallback_reason") or ""),
            gamma_coverage=_optional_float(result.get("gamma_coverage")),
            complete_status=str(result.get("complete_status") or "unavailable"),
            horizons=list(result.get("horizons") or []),
            term_structure=dict(result.get("term_structure") or {}),
        )
    except Exception as exc:
        return OptionContext(
            error_message=f"Option analysis failed: {exc}",
            status="failed",
            source="yfinance",
            is_partial=True,
            quality_warnings=[f"Option analysis failed: {exc}"],
            cache_status="failed",
        )


def _safe_call(callback, fallback, errors: list[str]):
    try:
        return callback()
    except Exception as exc:
        errors.append(str(exc))
        return fallback


def _run_stage_tasks(
    tasks: dict[str, Callable[[], Any]],
    errors: list[str],
    *,
    stage_name: str,
    max_workers: int,
    task_timeout_seconds: float = MARKET_STAGE_TASK_TIMEOUT_SECONDS,
    total_timeout_seconds: float = MARKET_STAGE_TOTAL_TIMEOUT_SECONDS,
) -> dict[str, StageTaskResult]:
    """Run stage tasks without allowing one provider to block the whole UI."""

    if not tasks:
        return {}

    executor = _MARKET_STAGE_EXECUTORS.get(max_workers)
    if executor is None:
        raise ValueError(f"Unsupported market stage worker count: {max_workers}")
    futures = {executor.submit(callback): name for name, callback in tasks.items()}
    pending = set(futures)
    results: dict[str, StageTaskResult] = {}
    deadline = time.monotonic() + total_timeout_seconds

    while pending:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            completed = as_completed(
                tuple(pending), timeout=min(task_timeout_seconds, remaining)
            )
            for future in completed:
                name = futures[future]
                pending.discard(future)
                try:
                    results[name] = StageTaskResult(value=future.result())
                except Exception as exc:
                    error = f"{stage_name}.{name} failed: {exc}"
                    errors.append(error)
                    results[name] = StageTaskResult(
                        status="failed",
                        error=error,
                    )
        except FutureTimeoutError:
            break

    for future in tuple(pending):
        name = futures[future]
        future.cancel()
        error = f"{stage_name}.{name} timed out after {task_timeout_seconds:g}s"
        errors.append(error)
        results[name] = StageTaskResult(
            status="timed_out",
            error=error,
            timed_out=True,
        )

    return {
        name: results.get(
            name,
            StageTaskResult(
                status="failed",
                error=f"{stage_name}.{name} did not return a result.",
            ),
        )
        for name in tasks
    }


def _stage_task_values(results: dict[str, StageTaskResult]) -> dict[str, Any]:
    return {
        name: result.value for name, result in results.items() if result.status == "ok"
    }


def _future_result(future, errors: list[str]):
    try:
        return future.result()
    except Exception as exc:
        errors.append(str(exc))
        return None


def _build_volatility_sentiment_context(
    market_type: str,
    *,
    ibd_regime: dict[str, Any],
    credit_stress: dict[str, Any],
) -> dict[str, Any]:
    """Build dependent volatility/sentiment outputs after their inputs are current."""

    if market_type != "US":
        return {}
    spy = get_stock_data("SPY", "5y")
    if spy is None or spy.empty:
        return {}
    tlt = get_stock_data("TLT", "1y")
    cboe = fetch_cboe_indices()
    cnn = fetch_cnn_fear_greed()
    return {
        "volatility_regime": build_market_volatility_regime(
            spy,
            cboe_result=cboe,
            credit_stress=credit_stress,
            ibd_regime=ibd_regime,
        ),
        "vix_sq_alert": build_vix_sq_alert_context(cboe.data if cboe else None),
        "sentiment": build_local_sentiment_composite(
            spy,
            tlt,
            cboe_result=cboe,
            credit_stress=credit_stress,
            cnn_reference=cnn,
        ),
    }


def _replace_data_status(
    existing: list[DataResult], *updates: DataResult
) -> list[DataResult]:
    """Keep one current status row per analysis feature."""

    by_name = {item.name: item for item in existing}
    for item in updates:
        by_name[item.name] = item
    return list(by_name.values())


def _normalize_microstructure(data: dict | None) -> dict[str, Any]:
    return data or {}


def _extract_spy_pcr(option_data: list[dict[str, Any]] | None) -> float | None:
    if not option_data:
        return None
    first = next(
        (item for item in option_data if item.get("ticker") == "SPY"),
        option_data[0],
    )
    pcr = first.get("pcr", {})
    if isinstance(pcr, dict):
        value = pcr.get("volume_pcr")
        return float(value) if isinstance(value, (int, float)) else None
    if isinstance(pcr, (int, float)):
        return float(pcr)
    return None


def _option_item(
    option_data: list[dict[str, Any]] | None, ticker: str
) -> dict[str, Any] | None:
    if not option_data:
        return None
    normalized = ticker.upper()
    for item in option_data:
        if str(item.get("ticker") or "").upper() == normalized:
            return item
    return None


def _extract_pe(info: dict[str, Any] | None) -> float | None:
    value = info.get("pe_ratio") if info else None
    return float(value) if isinstance(value, (int, float)) else None


def _nested(source: dict[str, Any], parent: str, child: str) -> str:
    value = source.get(parent) or {}
    return str(value.get(child, "unknown")) if isinstance(value, dict) else "unknown"


def _display_percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2%}"
    return "unknown"


def _ticker_list_text(value: Any) -> str:
    if not value:
        return "representative tickers unavailable"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value[:5])
    return str(value)


def _coerce_context(
    value: MarketContext | dict[str, Any] | None,
) -> MarketContext | None:
    if isinstance(value, MarketContext):
        return value
    if isinstance(value, dict) and value:
        return MarketContext.from_mapping(value)
    return None


def _merge_ibd_signal(
    evaluation: dict[str, Any],
    ibd_regime: dict[str, Any],
) -> dict[str, Any]:
    if not ibd_regime:
        return evaluation

    signals = list(evaluation.get("signals") or [])
    signals.append(
        {
            "name": "IBD市場状態",
            "score": float(ibd_regime.get("score", 0.0)),
            "weight": float(ibd_regime.get("weight", 2.0)),
            "rationale": str(ibd_regime.get("rationale") or ""),
        }
    )
    total_weight = sum(float(item.get("weight", 0.0)) for item in signals)
    score = (
        sum(
            float(item.get("score", 0.0)) * float(item.get("weight", 0.0))
            for item in signals
        )
        / total_weight
        if total_weight
        else float(evaluation.get("score", 0.0))
    )
    if score >= 0.3:
        status = "🟢 強気 (Bullish)"
        description = "IBD式市場状態を含む複合評価では、リスクを取りやすい環境である。"
    elif score <= -0.3:
        status = "🔴 弱気 (Bearish)"
        description = (
            "IBD式市場状態を含む複合評価では、資金防衛を優先すべき環境である。"
        )
    else:
        status = "⚪ 中立 (Neutral)"
        description = "IBD式市場状態を含む複合評価では、強弱が混在し選別が必要である。"

    return {
        **evaluation,
        "status": status,
        "score": score,
        "description": description,
        "signals": signals,
    }


def _context_cache_path(market_type: str, kind: str):
    return context_cache_path(_market_context_cache(), market_type, kind)


def _save_context_cache(context: MarketContext, kind: str) -> None:
    _sync_compat_dependencies()
    try:
        save_context_cache(
            _market_context_cache(),
            context,
            kind,
            fetched_at=context.fetched_at or _utc_now(),
        )
    except OSError:
        return


def _load_context_cache(
    market_type: str,
    kind: str,
    *,
    max_age_seconds: int,
    fresh_seconds: int,
) -> MarketContext | None:
    _sync_compat_dependencies()
    read = read_context_cache(
        _market_context_cache(),
        market_type,
        kind,
        fresh_seconds=fresh_seconds,
        stale_seconds=max_age_seconds,
    )
    if not read.is_available:
        return None

    context = context_from_cache_payload(read.payload)
    if read.fetched_at and not context.fetched_at:
        context.fetched_at = read.fetched_at
    context.source = f"{context.source or kind}_cache"
    context.is_stale = read.is_stale
    context.cache_status = "stale_cache" if read.is_stale else "persistent_cache"
    context.cache_age_seconds = read.age_seconds
    for item in context.data_status:
        item.cache_status = context.cache_status
        item.cache_age_seconds = read.age_seconds
    if context.is_stale:
        context.quality_warnings = _merge_warnings(
            context.quality_warnings,
            [f"Using cached market summary from {context.fetched_at}."],
        )
        context.provenance = _merge_provenance(
            context.provenance,
            [
                stale_cache_provenance(
                    fetched_at=context.fetched_at,
                    source=context.source,
                )
            ],
        )
    context.detail_stages = _cached_stage_statuses(
        context.detail_stages,
        read.is_stale,
        context.cache_status,
        read.fetched_at,
    )
    return context


def _updated_stage_statuses(
    existing: dict[str, dict[str, Any]] | None,
    key: str,
    status: str,
    *,
    cache_status: str = "",
    fetched_at: str = "",
    summary: str = "",
    error_message: str = "",
    warnings: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    stages = _default_stage_statuses()
    for stage_key, payload in (existing or {}).items():
        if isinstance(payload, dict):
            stages[stage_key] = {**stages.get(stage_key, {}), **payload}
    default = DETAIL_STAGE_DEFAULTS.get(key, {})
    stages[key] = {
        **stages.get(key, {}),
        "key": key,
        "label": default.get("label", key),
        "difficulty": default.get("difficulty", ""),
        "target": default.get("target", ""),
        "status": status,
        "status_label": _stage_status_label(status),
        "cache_status": cache_status,
        "fetched_at": fetched_at,
        "summary": summary or default.get("summary", ""),
        "error_message": error_message,
        "quality_warnings": _merge_warnings(warnings or []),
    }
    return {stage_key: stages[stage_key] for stage_key in DETAIL_STAGE_ORDER}


def _default_stage_statuses() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "key": key,
            "label": payload["label"],
            "difficulty": payload["difficulty"],
            "target": payload["target"],
            "status": "pending",
            "status_label": "未取得",
            "cache_status": "",
            "fetched_at": "",
            "summary": payload["summary"],
            "error_message": "",
            "quality_warnings": [],
        }
        for key, payload in DETAIL_STAGE_DEFAULTS.items()
    }


def _cached_stage_statuses(
    existing: dict[str, dict[str, Any]] | None,
    is_stale: bool,
    cache_status: str,
    fetched_at: str,
) -> dict[str, dict[str, Any]]:
    stages = _default_stage_statuses()
    for key, payload in (existing or {}).items():
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "pending")
        if status in {"live", "partial", "cache"}:
            status = "stale_cache" if is_stale else "cache"
        stages[key] = {
            **stages.get(key, {}),
            **payload,
            "status": status,
            "status_label": _stage_status_label(status),
            "cache_status": cache_status,
            "fetched_at": fetched_at or payload.get("fetched_at", ""),
        }
    return {stage_key: stages[stage_key] for stage_key in DETAIL_STAGE_ORDER}


def _stage_status_label(status: str) -> str:
    return {
        "pending": "未取得",
        "loading": "取得中",
        "live": "最新",
        "partial": "一部取得",
        "cache": "キャッシュ",
        "stale_cache": "古いキャッシュ",
        "failed": "取得失敗",
    }.get(status, status)


def _utc_now() -> str:
    return utc_now_iso()


def _merge_warnings(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = str(item)
            if text and text not in seen:
                merged.append(text)
                seen.add(text)
    return merged


def _merge_provenance(*groups):
    merged = {}
    for group in groups:
        for item in group or []:
            merged[item.item_id] = item
    return list(merged.values())


def _context_cache_key(market_type: str, kind: str) -> str:
    return context_cache_key(market_type, kind)


def _market_context_cache() -> PersistentJsonCache:
    return market_context_cache(MARKET_CONTEXT_CACHE_NAMESPACE)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _low_pe_relative_return_6m() -> float | None:
    """Return growth-minus-value six-month performance as the public proxy."""

    growth = get_stock_data("RPG", "1y")
    value = get_stock_data("RPV", "1y")
    if growth is None or value is None or growth.empty or value.empty:
        return None
    joined = pd.concat(
        [growth["Close"].rename("growth"), value["Close"].rename("value")],
        axis=1,
    ).dropna()
    if len(joined) < 126:
        return None
    return float(
        joined["growth"].iloc[-1] / joined["growth"].iloc[-126]
        - joined["value"].iloc[-1] / joined["value"].iloc[-126]
    )
