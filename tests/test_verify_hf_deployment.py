from __future__ import annotations

from dataclasses import dataclass

import pytest

from scripts.verify_hf_deployment import (
    FetchResult,
    VerificationError,
    preflight_space,
    verify_deployment,
)

EXPECTED_SHA = "a" * 40
OLD_SHA = "b" * 40
SPACE = "owner/space"
HEALTH_URL = "https://owner-space.hf.space/_health"
TOKEN = "hf_test_token_value"


@dataclass
class FakeClock:
    now: float = 0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def space_response(
    *, sha: str = EXPECTED_SHA, stage: str = "RUNNING", private: bool = True
) -> FetchResult:
    return FetchResult(
        200,
        {
            "private": private,
            "sha": sha,
            "runtime": {"stage": stage},
        },
    )


def test_old_revision_health_cannot_pass() -> None:
    health_calls = 0

    def fetch_health(_url: str, _token: str) -> FetchResult:
        nonlocal health_calls
        health_calls += 1
        return FetchResult(200, {"status": True})

    with pytest.raises(VerificationError, match="timed out"):
        verify_deployment(
            space=SPACE,
            expected_sha=EXPECTED_SHA,
            health_url=HEALTH_URL,
            token=TOKEN,
            require_private=True,
            timeout_seconds=0,
            fetch_space=lambda _url, _token: space_response(sha=OLD_SHA),
            fetch_health=fetch_health,
            emit=lambda _message: None,
        )

    assert health_calls == 0


def test_target_running_revision_with_valid_health_passes() -> None:
    result = verify_deployment(
        space=SPACE,
        expected_sha=EXPECTED_SHA,
        health_url=HEALTH_URL,
        token=TOKEN,
        require_private=True,
        timeout_seconds=0,
        fetch_space=lambda _url, _token: space_response(),
        fetch_health=lambda _url, _token: FetchResult(200, {"status": True}),
        emit=lambda _message: None,
    )

    assert result.observed_sha == EXPECTED_SHA
    assert result.runtime_stage == "RUNNING"
    assert result.health_status == 200


def test_target_runtime_error_fails_immediately_and_redacts_secrets() -> None:
    supabase_secret = "sb_secret_should_not_appear"
    payload = {
        "private": True,
        "sha": EXPECTED_SHA,
        "runtime": {
            "stage": "RUNTIME_ERROR",
            "errorMessage": (
                f"Authorization: Bearer {TOKEN} SUPABASE_SECRET_KEY={supabase_secret}"
            ),
        },
    }

    with pytest.raises(VerificationError) as captured:
        verify_deployment(
            space=SPACE,
            expected_sha=EXPECTED_SHA,
            health_url=HEALTH_URL,
            token=TOKEN,
            require_private=True,
            timeout_seconds=900,
            fetch_space=lambda _url, _token: FetchResult(200, payload),
            fetch_health=lambda _url, _token: pytest.fail(
                "health must not run after RUNTIME_ERROR"
            ),
            sleep=lambda _seconds: pytest.fail("RUNTIME_ERROR must fail immediately"),
            emit=lambda _message: None,
        )

    message = str(captured.value)
    assert "RUNTIME_ERROR" in message
    assert TOKEN not in message
    assert supabase_secret not in message


def test_health_000_and_503_retry_until_target_is_healthy() -> None:
    clock = FakeClock()
    responses = iter(
        [
            FetchResult(0),
            FetchResult(503),
            FetchResult(200, {"status": True}),
        ]
    )

    result = verify_deployment(
        space=SPACE,
        expected_sha=EXPECTED_SHA,
        health_url=HEALTH_URL,
        token=TOKEN,
        require_private=True,
        timeout_seconds=5,
        poll_interval_seconds=1,
        fetch_space=lambda _url, _token: space_response(),
        fetch_health=lambda _url, _token: next(responses),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        emit=lambda _message: None,
    )

    assert result.health_status == 200
    assert clock.now == 2


def test_building_revision_retries_then_reports_deadline() -> None:
    clock = FakeClock()
    stages: list[str] = []

    with pytest.raises(VerificationError) as captured:
        verify_deployment(
            space=SPACE,
            expected_sha=EXPECTED_SHA,
            health_url=HEALTH_URL,
            token=TOKEN,
            require_private=True,
            timeout_seconds=2,
            poll_interval_seconds=1,
            fetch_space=lambda _url, _token: space_response(stage="BUILDING"),
            fetch_health=lambda _url, _token: pytest.fail(
                "health must wait until RUNNING"
            ),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            emit=stages.append,
        )

    assert "timed out" in str(captured.value)
    assert "stage=BUILDING" in str(captured.value)
    assert len(stages) == 3


def test_missing_token_fails_before_network() -> None:
    called = False

    def fetch_space(_url: str, _token: str) -> FetchResult:
        nonlocal called
        called = True
        return space_response()

    with pytest.raises(VerificationError, match="HF_TOKEN"):
        preflight_space(
            space=SPACE,
            token="",
            require_private=True,
            fetch_space=fetch_space,
        )

    assert called is False


def test_public_space_fails_preflight() -> None:
    with pytest.raises(VerificationError, match="not private"):
        preflight_space(
            space=SPACE,
            token=TOKEN,
            require_private=True,
            fetch_space=lambda _url, _token: space_response(private=False),
        )
