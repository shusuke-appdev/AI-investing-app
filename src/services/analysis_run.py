"""Reproducible analysis-run artifacts for UI and AI outputs."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from pydantic import BaseModel

from src.persistent_cache import utc_now_iso
from src.services.analysis_context import DataResult


@dataclass
class AnalysisRun:
    """One reproducible record of data inputs, analysis outputs, and warnings."""

    kind: str
    subject: str
    inputs: dict[str, Any] = field(default_factory=dict)
    data_status: list[DataResult] = field(default_factory=list)
    generated_signal: dict[str, Any] = field(default_factory=dict)
    prompt_summary: str = ""
    ai_output: str = ""
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "kind": self.kind,
            "subject": self.subject,
            "created_at": self.created_at,
            "inputs": _plain(self.inputs),
            "data_status": [item.to_dict() for item in self.data_status],
            "generated_signal": _plain(self.generated_signal),
            "prompt_summary": self.prompt_summary,
            "ai_output": self.ai_output,
            "warnings": list(self.warnings),
            "metadata": _plain(self.metadata),
        }

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> AnalysisRun:
        return cls(
            run_id=str(value.get("run_id") or uuid.uuid4()),
            kind=str(value.get("kind") or ""),
            subject=str(value.get("subject") or ""),
            created_at=str(value.get("created_at") or utc_now_iso()),
            inputs=dict(value.get("inputs") or {}),
            data_status=[
                DataResult(
                    name=str(item.get("name") or ""),
                    source=str(item.get("source") or ""),
                    fetched_at=str(item.get("fetched_at") or ""),
                    is_stale=bool(item.get("is_stale", False)),
                    is_partial=bool(item.get("is_partial", False)),
                    error=str(item.get("error") or ""),
                    cache_status=str(item.get("cache_status") or "live"),
                    cache_age_seconds=item.get("cache_age_seconds"),
                )
                for item in value.get("data_status", [])
                if isinstance(item, dict)
            ],
            generated_signal=dict(value.get("generated_signal") or {}),
            prompt_summary=str(value.get("prompt_summary") or ""),
            ai_output=str(value.get("ai_output") or ""),
            warnings=list(value.get("warnings") or []),
            metadata=dict(value.get("metadata") or {}),
        )

    def to_markdown(self) -> str:
        lines = [
            f"# Analysis Run: {self.kind} / {self.subject}",
            "",
            f"- Run ID: {self.run_id}",
            f"- Created at: {self.created_at}",
            "",
            "## Data Status",
        ]
        if not self.data_status:
            lines.append("- No data status recorded.")
        for item in self.data_status:
            state = "partial" if item.is_partial else "ok"
            if item.is_stale:
                state = "stale"
            lines.append(
                f"- {item.name}: {state}; source={item.source}; "
                f"cache={item.cache_status}; error={item.error or '-'}"
            )
        lines.extend(
            [
                "",
                "## Inputs",
                _json_block(self.inputs),
                "",
                "## Generated Signal",
                _json_block(self.generated_signal),
                "",
                "## Prompt Summary",
                self.prompt_summary or "-",
                "",
                "## AI Output",
                self.ai_output or "-",
            ]
        )
        if self.warnings:
            lines.extend(["", "## Warnings", *[f"- {item}" for item in self.warnings]])
        return "\n".join(lines)

    def to_notebook_json(self) -> dict[str, Any]:
        return {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"analysis_run": self.to_dict()},
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": self.to_markdown().splitlines(keepends=True),
                }
            ],
        }


def _plain(value: Any) -> Any:
    if isinstance(value, DataResult):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _json_block(value: Any) -> str:
    return (
        "```json\n"
        + json.dumps(_plain(value), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```"
    )
