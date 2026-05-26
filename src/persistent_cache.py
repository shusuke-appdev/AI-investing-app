"""Repo-local JSON persistent cache utilities."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.log_config import get_logger

logger = get_logger(__name__)

CACHE_SCHEMA_VERSION = 1
_SAFE_KEY_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class PersistentCacheRead:
    """永続JSONキャッシュの読み取り結果。"""

    key: str
    namespace: str
    path: Path
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = ""
    age_seconds: float | None = None
    warning: str = ""

    @property
    def is_available(self) -> bool:
        """利用可能なfresh/staleキャッシュならTrue。"""

        return self.status in {"fresh", "stale"}

    @property
    def is_stale(self) -> bool:
        """stale扱いのキャッシュならTrue。"""

        return self.status == "stale"


class PersistentJsonCache:
    """`.states` 配下のJSONキャッシュを原子的に読み書きする。"""

    def __init__(self, root: Path, namespace: str) -> None:
        self.root = root
        self.namespace = namespace

    def path_for_key(self, key: str) -> Path:
        """キャッシュキーに対応する安全なJSONパスを返す。"""

        return self.root / f"{safe_cache_key(key)}.json"

    def write(
        self, key: str, payload: dict[str, Any], *, fetched_at: str | None = None
    ) -> Path:
        """payloadをschema付きJSONとして原子的に保存する。"""

        return self.write_path(
            self.path_for_key(key), key, payload, fetched_at=fetched_at
        )

    def write_path(
        self,
        path: Path,
        key: str,
        payload: dict[str, Any],
        *,
        fetched_at: str | None = None,
    ) -> Path:
        """指定パスへpayloadをschema付きJSONとして原子的に保存する。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        fetched = fetched_at or utc_now_iso()
        wrapped = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "namespace": self.namespace,
            "key": key,
            "fetched_at": fetched,
            "data": payload,
        }
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(wrapped, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        tmp_path.replace(path)
        return path

    def read(
        self,
        key: str,
        *,
        fresh_seconds: int,
        stale_seconds: int | None = None,
    ) -> PersistentCacheRead:
        """キャッシュを読み、fresh/stale/expired等の状態付きで返す。"""

        return self.read_path(
            self.path_for_key(key),
            key,
            fresh_seconds=fresh_seconds,
            stale_seconds=stale_seconds,
        )

    def read_path(
        self,
        path: Path,
        key: str,
        *,
        fresh_seconds: int,
        stale_seconds: int | None = None,
    ) -> PersistentCacheRead:
        """指定パスのキャッシュを読み、状態付きで返す。"""

        if not path.exists():
            return PersistentCacheRead(
                key=key, namespace=self.namespace, path=path, status="missing"
            )

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("[PersistentCache] Failed to read %s: %s", path, exc)
            return PersistentCacheRead(
                key=key,
                namespace=self.namespace,
                path=path,
                status="invalid",
                warning=str(exc),
            )

        if not isinstance(raw, dict):
            return PersistentCacheRead(
                key=key,
                namespace=self.namespace,
                path=path,
                status="invalid",
                warning="cache payload is not a JSON object",
            )

        payload, fetched_at = self._unwrap_payload(raw)
        age = age_seconds(fetched_at)
        if age is None:
            return PersistentCacheRead(
                key=key,
                namespace=self.namespace,
                path=path,
                status="invalid",
                payload=payload,
                fetched_at=fetched_at,
                warning="cache fetched_at is missing or invalid",
            )

        status = _classify_age(age, fresh_seconds, stale_seconds)
        return PersistentCacheRead(
            key=key,
            namespace=self.namespace,
            path=path,
            status=status,
            payload=payload if status in {"fresh", "stale"} else {},
            fetched_at=fetched_at,
            age_seconds=age,
        )

    def _unwrap_payload(self, raw: dict[str, Any]) -> tuple[dict[str, Any], str]:
        if raw.get("schema_version") == CACHE_SCHEMA_VERSION and isinstance(
            raw.get("data"), dict
        ):
            data = dict(raw["data"])
            fetched_at = str(raw.get("fetched_at") or data.get("fetched_at") or "")
            return data, fetched_at
        return raw, str(raw.get("fetched_at") or "")


def repo_state_cache(namespace: str) -> PersistentJsonCache:
    """リポジトリ標準の `.states/<namespace>` キャッシュを返す。"""

    root = Path(__file__).resolve().parents[1] / ".states" / namespace
    return PersistentJsonCache(root=root, namespace=namespace)


def safe_cache_key(key: str) -> str:
    """ファイル名に使える安全なキャッシュキーへ正規化する。"""

    safe = _SAFE_KEY_PATTERN.sub("_", str(key).strip())
    safe = safe.strip("._")
    return safe or "cache"


def utc_now_iso() -> str:
    """UTC現在時刻をISO文字列で返す。"""

    return datetime.now(timezone.utc).isoformat()


def age_seconds(fetched_at: str) -> float | None:
    """ISO時刻文字列の現在からの経過秒を返す。"""

    if not fetched_at:
        return None
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except ValueError:
        return None
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    return age if age >= 0 else None


def _classify_age(age: float, fresh_seconds: int, stale_seconds: int | None) -> str:
    if age <= fresh_seconds:
        return "fresh"
    if stale_seconds is not None and age <= stale_seconds:
        return "stale"
    return "expired"
