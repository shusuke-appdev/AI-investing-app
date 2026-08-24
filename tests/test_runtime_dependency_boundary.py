import subprocess
from pathlib import Path

import yaml


def test_active_reflex_runtime_does_not_import_streamlit():
    active_roots = (Path("frontend"), Path("src"))
    violations = []

    for root in active_roots:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "import streamlit" in source or "from streamlit" in source:
                violations.append(str(path))

    assert violations == []


def test_streamlit_is_not_a_current_dependency():
    dependency_files = (Path("requirements.txt"), Path("constraints.txt"))

    for path in dependency_files:
        assert "streamlit" not in path.read_text(encoding="utf-8").lower()


def test_mypy_is_development_only_and_pinned():
    runtime = Path("requirements.txt").read_text(encoding="utf-8").lower()
    development = Path("requirements-dev.txt").read_text(encoding="utf-8").lower()
    constraints = Path("constraints.txt").read_text(encoding="utf-8").lower()

    assert "mypy" not in runtime
    assert "mypy" in development
    assert "mypy==2.3.0" in constraints


def test_playwright_is_development_only_and_pinned():
    runtime = Path("requirements.txt").read_text(encoding="utf-8").lower()
    development = Path("requirements-dev.txt").read_text(encoding="utf-8").lower()
    constraints = Path("constraints.txt").read_text(encoding="utf-8").lower()

    assert "playwright" not in runtime
    assert "playwright" in development
    assert "playwright==1.61.0" in constraints


def test_pyyaml_is_development_only_and_pinned():
    runtime = Path("requirements.txt").read_text(encoding="utf-8").lower()
    development = Path("requirements-dev.txt").read_text(encoding="utf-8").lower()
    constraints = Path("constraints.txt").read_text(encoding="utf-8").lower()

    assert "pyyaml" not in runtime
    assert "pyyaml" in development
    assert "pyyaml==6.0.3" in constraints


def test_hugging_face_deploy_is_serialized_and_health_checked():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    workflow_data = yaml.safe_load(workflow)

    assert isinstance(workflow_data, dict)
    assert isinstance(workflow_data.get("jobs"), dict)
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow
    assert "environment: hugging-face-production" in workflow
    assert "HF_SPACE_REPO:" in workflow
    assert "HF_SPACE_READ_TOKEN:" in workflow
    assert workflow.index("Verify private Space before push") < workflow.index(
        "id: deploy"
    )
    assert "--preflight-only" in workflow
    assert "--require-private" in workflow
    assert "hf_deploy_commit=" in workflow
    assert "steps.deploy.outputs.hf_commit" in workflow
    assert "--expected-sha" in workflow
    assert "--timeout-seconds 900" in workflow
    assert "Verify deployed Space" in workflow
    assert "previous_hf_commit=" in workflow
    assert "Restore previous Space revision" in workflow
    assert "Preserve failed deployment result" in workflow


def test_hf_staging_acceptance_is_manual_isolated_and_fail_closed():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    production_job, staging_job = workflow.split("  sync-to-hub-staging:", maxsplit=1)

    assert "workflow_dispatch:" in workflow
    assert "rollback-exercise" in staging_job
    assert "environment: hugging-face-staging" in staging_job
    assert "inputs.staging_acceptance != 'quality-only'" in staging_job
    assert "HF_PRODUCTION_SPACE_REPO" in staging_job
    assert "HF_STAGING_ACCEPTANCE_ACK" in staging_job
    assert '"STAGING:${HF_SPACE_REPO}"' in staging_job
    assert "Staging and production Spaces must be different" in staging_job
    assert "--staging-force-health-failure" in staging_job
    assert "Restore previous staging revision" in staging_job
    assert "Preserve failed staging deployment result" in staging_job
    assert "--staging-force-health-failure" not in production_job


def test_operations_matches_current_staging_and_backup_contracts():
    operations = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")

    assert ".states/supabase_backups/" in operations
    assert "data/supabase_backups/` にバックアップ" not in operations
    assert "HF_SPACE_HEALTH_URL" not in operations
    assert "古い実行をキャンセルしてからforce push" not in operations
    assert "hugging-face-staging" in operations
    assert "supabase_staging_acceptance.py" in operations


def test_docker_runtime_is_non_root_and_excludes_build_toolchain():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    pinned_base = (
        "python:3.12-slim@sha256:"
        "2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a"
    )
    runtime = dockerfile.split(f"FROM {pinned_base} AS runtime", maxsplit=1)[1]

    assert f"FROM {pinned_base} AS builder" in dockerfile
    assert "COPY requirements-lock.txt ./" in dockerfile
    assert "pip==25.3 setuptools==82.0.1 wheel==0.48.0" in dockerfile
    assert "USER appuser" in runtime
    assert "HEALTHCHECK" in runtime
    assert "127.0.0.1:7860/_health" in runtime
    assert "mkdir -p /app/.web" in runtime
    assert "chown appuser:appuser /app" in runtime
    assert "build-essential" not in runtime
    assert "python3-dev" not in runtime


def test_ci_actions_and_dependency_install_are_immutable():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in workflow
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in workflow
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    )
    assert "python -m pip install -r requirements-dev-lock.txt" in workflow
    assert "python -m pip install --upgrade pip" not in workflow


def test_hf_force_push_rollback_restores_previous_revision_locally(tmp_path):
    remote = tmp_path / "space.git"
    worktree = tmp_path / "deploy"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "init", "-b", "main", str(worktree)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.name", "rollback-test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    deployed = worktree / "revision.txt"
    deployed.write_text("previous", encoding="utf-8")
    subprocess.run(["git", "-C", str(worktree), "add", "revision.txt"], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-m", "previous"], check=True)
    previous = subprocess.check_output(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"], text=True
    ).strip()
    subprocess.run(
        ["git", "-C", str(worktree), "push", str(remote), "main"], check=True
    )

    deployed.write_text("failed", encoding="utf-8")
    subprocess.run(["git", "-C", str(worktree), "commit", "-am", "failed"], check=True)
    subprocess.run(
        ["git", "-C", str(worktree), "push", "--force", str(remote), "main"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(worktree),
            "push",
            "--force",
            str(remote),
            f"{previous}:refs/heads/main",
        ],
        check=True,
    )

    restored = subprocess.check_output(
        ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"],
        text=True,
    ).strip()
    assert restored == previous


def test_direct_and_transitive_dependencies_are_fully_pinned():
    for path in (Path("requirements.txt"), Path("requirements-dev.txt")):
        specifications = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith(("#", "-r "))
        ]
        assert specifications
        assert all("==" in specification for specification in specifications)

    runtime_lock = Path("requirements-lock.txt").read_text(encoding="utf-8")
    development_lock = Path("requirements-dev-lock.txt").read_text(encoding="utf-8")
    assert "pytest==" not in runtime_lock
    assert "playwright==" not in runtime_lock
    assert "pytest==9.0.3" in development_lock
    assert "playwright==1.61.0" in development_lock


def test_market_dashboard_extracted_modules_have_explicit_dependencies():
    for path in (
        Path("src/services/market_dashboard_support.py"),
        Path("src/services/market_dashboard_workflows.py"),
    ):
        source = path.read_text(encoding="utf-8")
        assert "import *" not in source
        assert "_sync_compat_dependencies" not in source


def test_ci_builds_and_health_checks_the_docker_image():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "Build and smoke Docker image" in workflow
    assert "docker build --tag" in workflow
    assert "APP_MODE" not in workflow
    assert "http://127.0.0.1:7860/_health" in workflow
    assert "docker rm --force" in workflow
