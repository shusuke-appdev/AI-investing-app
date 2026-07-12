from pathlib import Path


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
