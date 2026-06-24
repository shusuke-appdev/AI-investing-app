"""Run the repository's read-only release checks."""

from __future__ import annotations

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


def main() -> int:
    """Run the same non-mutating checks used for local release validation."""

    reflex = repo_local_tool("reflex")
    if not reflex.exists():
        print(f"ERROR: Reflex executable not found beside Python: {reflex}")
        print("Install the pinned dependencies before running this script.")
        return 1

    checks = [
        ([sys.executable, "-m", "pip", "check"], "Dependency consistency"),
        (
            [sys.executable, "-m", "compileall", "-q", "src", "frontend", "tests"],
            "Python compilation",
        ),
        ([sys.executable, "-m", "ruff", "check", "."], "Ruff lint"),
        (
            [sys.executable, "-m", "ruff", "format", "--check", "."],
            "Ruff format check",
        ),
        ([sys.executable, "-m", "pytest", "-q"], "Pytest"),
        (
            [str(reflex), "export", "--frontend-only", "--no-zip"],
            "Reflex frontend export",
        ),
    ]
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
