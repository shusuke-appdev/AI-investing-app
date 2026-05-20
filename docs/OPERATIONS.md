# 運用・環境設定ガイド

## 必須ランタイム

- Python 3.12 推奨
- PowerShell または互換シェル
- Docker を使う場合は Docker Desktop

## 環境変数

| 変数 | 必須度 | 用途 |
| --- | --- | --- |
| `GEMINI_API_KEY` | AI機能には必須 | Gemini による市況・銘柄・ポートフォリオ分析 |
| `FINNHUB_API_KEY` | 推奨 | 企業ニュース、決算、オプション補完データ |
| `JQUANTS_API_KEY` | 日本株分析では推奨 | 日本株の価格・財務情報 |
| `EDINET_API_KEY` | 日本株財務では推奨 | EDINET からの財務情報取得 |
| `SUPABASE_URL` | Supabase保存時に必須 | ポートフォリオ・知識DB保存先 |
| `SUPABASE_KEY` | Supabase保存時に必須 | Supabase APIキー |

## ローカル起動

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
reflex run
```

旧UIを確認する場合:

```powershell
streamlit run legacy_streamlit/app.py
```

## Docker起動

```powershell
docker build -t ai-investing-app .
docker run --env-file .env -p 7860:7860 ai-investing-app
```

Dockerfile は Hugging Face Spaces の 7860 番ポートを前提にしています。

## 定期的な確認コマンド

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

外部APIに依存する確認は失敗しやすいため、単体テストではモックを優先します。実API確認は `scripts/debug/` と `scripts/verify/` を用途別に使います。

## データ保存先

### ローカル

- ポートフォリオ: `data/portfolios/*.json`
- 知識DB: `data/knowledge*.json` 系のローカルファイル
- キャッシュ: `app_cache.sqlite`、`yfinance_cache.sqlite`

### GAS

Google Apps Script の Web App URL を設定すると、GAS 経由でポートフォリオと知識を保存できます。設定手順は `GAS_SETUP.md` を参照してください。

### Supabase

`SUPABASE_URL` と `SUPABASE_KEY` を設定すると Supabase に保存できます。現在のコードは `portfolios`、`knowledge_items`、`user_settings` テーブルを前提にしています。

## 運用上の注意

- 外部APIの制限により、オプション分析とニュース集約は一時的に空になることがあります
- `yfinance` など外部データソースのレスポンススキーマは変更されることがあり、列名の変化に備えたテストが必要です
- AIレポートは入力データに依存するため、データ取得失敗時にはレポート品質も低下します
- `.env`、SQLiteキャッシュ、アップロードファイル、生成zipは原則としてGit管理しません
- GitHub Actions の Hugging Face Spaces 同期は `main` / `master` への push で force push します。運用前に対象Spaceとブランチ保護を確認してください

## 既知のローカル環境問題

2026-05-14 に、`.venv\Scripts\python.exe` が `Unable to create process` で起動できない問題を復旧しました。原因は `.venv` が存在しない Python インストール先を参照していたことです。

現在の `.venv\pyvenv.cfg` は `C:\tmp\Python312\python.exe` を Python 本体として参照しています。`py -3.12` もこの Python を指すように登録済みです。新しく開いたターミナルでは `python` もユーザーPATHから解決できます。

このワークスペースでは通常どおり以下のコマンドが使えます。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall src frontend tests
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
```

`pytest` のキャッシュは、アクセス拒否が発生していた `.pytest_cache` ではなく `.states/pytest_cache` を使うように設定済みです。
`ruff` のキャッシュも `.states/ruff_cache` を使います。

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt
```

削除前に、ローカルだけで必要な仮想環境内ファイルがないことを確認してください。
