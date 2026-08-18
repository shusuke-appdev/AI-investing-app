"""Run the repository's read-only release checks."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """Run one check without installing dependencies or rewriting files."""

    print(f"\n[Code Factory] {description}: {' '.join(command)}")
    try:
        completed = subprocess.run(command, check=False, text=True)
    except OSError as exc:
        print(f"ERROR: {description}: {exc}")
        return False
    if completed.returncode != 0:
        print(f"FAILED: {description} (exit={completed.returncode})")
        return False
    print(f"PASSED: {description}")
    return True


def repo_local_tool(name: str) -> Path:
    """Resolve a console script next to the active virtualenv Python."""

    suffix = ".exe" if os.name == "nt" else ""
    return Path(sys.executable).resolve().parent / f"{name}{suffix}"


def _pytest_command(*, coverage: bool, quick: bool) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        f"--basetemp=.states/pytest_tmp_{os.getpid()}",
    ]
    if quick:
        return [*command, "-m", "not integration and not slow"]
    if coverage:
        return [
            *command,
            "--cov=src",
            "--cov=frontend",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=html:.states/coverage_html",
            "--cov-report=json:.states/coverage.json",
            "--cov-fail-under=67",
        ]
    return command


def _checks(*, coverage: bool, quick: bool) -> list[tuple[list[str], str]]:
    reflex = repo_local_tool("reflex")
    checks = [
        (
            [sys.executable, "-m", "compileall", "-q", "src", "frontend", "tests"],
            "Python compilation",
        ),
        ([sys.executable, "-m", "ruff", "check", "."], "Ruff lint"),
        (
            [sys.executable, "-m", "ruff", "format", "--check", "."],
            "Ruff format check",
        ),
        (
            [
                sys.executable,
                "-m",
                "mypy",
                "src/provider_result.py",
                "src/deployment_guard.py",
                "src/services/analysis_context.py",
                "src/services/market_analysis_inputs.py",
                "src/services/market_dashboard_support.py",
                "src/services/market_dashboard_workflows.py",
                "src/theme_analyst.py",
                "frontend/state/error_handling.py",
            ],
            "Mypy critical contracts",
        ),
        (
            _pytest_command(coverage=coverage, quick=quick),
            "Pytest coverage" if coverage else "Pytest quick" if quick else "Pytest",
        ),
    ]
    if quick:
        return checks
    return [
        ([sys.executable, "-m", "pip", "check"], "Dependency consistency"),
        *checks,
        (
            [str(reflex), "export", "--frontend-only", "--no-zip"],
            "Reflex frontend export",
        ),
        (
            [sys.executable, "scripts/ui_static_smoke.py"],
            "Static UI semantics",
        ),
    ]


def main() -> int:
    """Run the same non-mutating checks used for local release validation."""

    parser = argparse.ArgumentParser()
    profile = parser.add_mutually_exclusive_group()
    profile.add_argument(
        "--quick",
        action="store_true",
        help="Run compile, Ruff, and hermetic tests excluding integration/slow markers.",
    )
    profile.add_argument(
        "--coverage",
        action="store_true",
        help="Run the full release gate and write branch coverage under .states/.",
    )
    args = parser.parse_args()
    reflex = repo_local_tool("reflex")
    if not args.quick and not reflex.exists():
        print(f"ERROR: Reflex executable not found beside Python: {reflex}")
        print("Install the pinned dependencies before running this script.")
        return 1
    if not repo_local_tool("mypy").exists():
        print("ERROR: mypy executable not found beside Python.")
        print("Install the pinned development dependencies before running this script.")
        return 1

    checks = _checks(coverage=args.coverage, quick=args.quick)
    failures = [
        description
        for command, description in checks
        if not run_command(command, description)
    ]
    if failures:
        print("\nChecks completed with issues: " + ", ".join(failures))
        return 1
    print("\nAll read-only release checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
