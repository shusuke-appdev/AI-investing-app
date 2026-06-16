from pathlib import Path


def test_dockerignore_excludes_local_secrets_and_personal_data():
    patterns = {
        line.strip()
        for line in Path(".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    required = {
        ".env",
        ".env.*",
        "*.key",
        "*.pem",
        "secrets",
        "**/.streamlit/secrets.toml",
        "data/*.json",
        "data/*.csv",
        "data/portfolio_history",
        "data/supabase_backups",
        "uploaded_files",
        "downloads",
    }

    assert required <= patterns
