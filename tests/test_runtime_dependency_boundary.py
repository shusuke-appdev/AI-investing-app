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
    assert "cancel-in-progress: true" in workflow
    assert "environment: hugging-face-production" in workflow
    assert "HF_SPACE_REPO:" in workflow
    assert "HF_SPACE_HEALTH_URL:" in workflow
    assert ".hf.space/_health" in workflow
    assert "Verify deployed Space" in workflow
    assert "previous_hf_commit=" in workflow


def test_docker_runtime_is_non_root_and_excludes_build_toolchain():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    runtime = dockerfile.split("FROM python:3.12-slim AS runtime", maxsplit=1)[1]

    assert "FROM python:3.12-slim AS builder" in dockerfile
    assert "USER appuser" in runtime
    assert "HEALTHCHECK" in runtime
    assert "127.0.0.1:7860/_health" in runtime
    assert "build-essential" not in runtime
    assert "python3-dev" not in runtime
