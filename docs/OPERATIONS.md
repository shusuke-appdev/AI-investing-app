# 運用・環境設定ガイド

## 必須ランタイム

- Python 3.12 推奨
- PowerShell または互換シェル
- Docker を使う場合は Docker Desktop

## 環境変数

| 変数 | 必須度 | 用途 |
| --- | --- | --- |
| `GEMINI_API_KEY` | AI機能には必須 | Gemini による市況・銘柄・ポートフォリオ分析 |
| `GEMINI_MODEL_NAME` / `GEMINI_MODEL` | 任意 | Geminiモデル名の上書き。未設定時は `gemini-3.5-flash` |
| `FINNHUB_API_KEY` | 推奨 | 企業ニュース、決算、オプション補完データ |
| `JQUANTS_API_KEY` | 日本株分析では推奨 | 日本株の価格・財務情報 |
| `EDINET_API_KEY` | 日本株財務では推奨 | EDINET からの財務情報取得 |
| `NIKKEI_JSF_SHORT_BALANCE_BILLION` | 任意 | 日経6条件の条件1を直接判定するための、日証金合計売り残（億円） |
| `NIKKEI_LEVERAGE_MARGIN_RATIO` | 任意 | 日経6条件の条件2を直接判定するための、日経レバ1570信用倍率 |
| `NIKKEI_FOREIGN_INVESTOR_NET_BUY_BILLION` | 任意 | 日経6条件の条件6を直接判定するための、海外投資家買越額（億円） |
| `SUPABASE_URL` | Supabase保存時に必須 | ポートフォリオ・知識DB保存先 |
| `SUPABASE_SECRET_KEY` | Supabase保存時に推奨 | サーバー側 Supabase Data API 用の secret key。クライアントへ公開しない |
| `SUPABASE_SERVICE_ROLE_KEY` | 任意 | 旧 service role key との互換用。`SUPABASE_SECRET_KEY` が未設定の場合だけ使う |
| `SUPABASE_KEY` | 任意 | 旧設定との互換用キー。上記2つが未設定の場合だけ使う |

## ローカル起動

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -c constraints.txt
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
- HTTPキャッシュ: `.states/http_cache/app_cache.sqlite` など用途別SQLite
- yfinanceタイムゾーンキャッシュ: `.states/yfinance_cache/`
- 市場サマリーキャッシュ: `.states/market_context_cache/*.json`
- オプションチェーンキャッシュ: `.states/option_chain_cache/*.json`
- 分析ジョブ状態: `.states/analysis_jobs/*.json`

### GAS

Google Apps Script の Web App URL を設定すると、GAS 経由でポートフォリオと知識を保存できます。設定手順は `GAS_SETUP.md` を参照してください。

### Supabase

`SUPABASE_URL` と `SUPABASE_SECRET_KEY` を設定すると Supabase に保存できます。旧設定との互換のため `SUPABASE_SERVICE_ROLE_KEY` と `SUPABASE_KEY` も読みますが、新規環境では secret key をサーバー環境変数として使います。現在のコードは `portfolios`、`knowledge_items`、`user_settings` テーブルを前提にしています。

Supabase の 2026-05-30 / 2026-10-30 の Data API 既定変更に対応するため、新規 Supabase プロジェクトまたは新規テーブル作成時は、データ移行前に [supabase/public_tables.sql](../supabase/public_tables.sql) を Supabase SQL Editor で実行してください。移行ツールからも同じ SQL を表示できます。この SQL は `postgres` ロールが今後作る `public` オブジェクトの自動 Data API 公開も抑止します。

```powershell
python tools/migrate_to_supabase.py --print-setup-sql
```

詳細は [Supabase Data API grants 対応](SUPABASE_DATA_API_GRANTS.md) を参照してください。

## 運用上の注意

- 外部APIの制限により、オプション分析とニュース集約は一時的に空になることがあります
- Market Intelligence の起動時は軽量サマリーのみ自動取得します。詳細分析はサイドバーの「市場監視」で「詳細更新」、SPY / QQQ / IWM のオプション取得は「Options」ボタンで明示的に実行します
- 「市場監視」には、IBD式市場状態、状態別プレイブック、総合市場監視、テーマモメンタム、詳細テーマランキング、オプション分析、市場の歪み検知を統合しています。旧「Theme」独立ページはサイドバーから外しています
- IBD式市場状態は無料データによる近似です。公式IBD Market Pulseではなく、SPY / Nasdaq 100 の売り抜け日、ラリー試行、FTD、移動平均割れから分類します
- Market Recap では「＋」ボタンから任意の追加分析項目を入力できます。入力内容はプロンプトに渡され、現在の市場状態、フロー、ファンダメンタル、反証条件に結び付けて分析されます
- 「詳細更新」では、米国セクターETFと日本テーマバスケットから資金流入セクターを推定し、確信度・継続性・調査判断を表示します。これは売買命令ではなく、市場分析の入力です
- 日経平均上昇の6条件は、無料で自動取得できるデータを優先し、直接データがない条件は `データ不足` または `代理達成/代理未達` として表示します。上記の任意環境変数を設定すると、一部条件を直接値として評価できます
- AI Market Recap は米国市場を主軸にし、日本市場は米国市場との相対強弱、日経6条件、ドル円・原油・資金流入の文脈で補助的に扱います
- yfinanceオプションデータにGreeks/Gammaがない場合、GEXは非表示になります。UIの `data_quality` バッジと品質警告を確認してください
- キャッシュ由来のデータは `source`、`fetched_at`、`is_stale`、`cache_status`、`quality_warnings` としてUI/AIへ渡します。`stale_cache` 表示がある場合は、外部API失敗時に最後の成功データを使っています
- 時系列データを突合する場合は `src/services/temporal_alignment.py` の as-of join を使い、許容時間差外の未突合行を `DataResult.is_partial` と `quality_warnings` で明示します
- 重い分析処理は `src/services/analysis_jobs.py` の `queued/running/succeeded/failed/partial/cancelled` 状態で管理し、単一Reflex環境ではローカルJSON永続化を使います
- `yfinance` など外部データソースのレスポンススキーマは変更されることがあり、列名の変化に備えたテストが必要です
- AIレポートは入力データに依存するため、データ取得失敗時にはレポート品質も低下します
- `.env`、SQLiteキャッシュ、アップロードファイル、生成zipは原則としてGit管理しません
- GitHub Actions の Hugging Face Spaces 同期は `main` / `master` への push で force push します。運用前に対象Spaceとブランチ保護を確認してください
- Supabase移行は既定でdry-runです。実行は `python tools/migrate_to_supabase.py --execute`、既存テーブルを消して入れ替える場合のみ `--confirm-destroy` を追加します。破壊実行時は `data/supabase_backups/` にバックアップが取れない限り中断します。新規テーブル作成が必要な場合は、先に `python tools/migrate_to_supabase.py --print-setup-sql` で表示される SQL を Supabase SQL Editor で実行します。

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

ローカルキャッシュを初期化したい場合は、アプリを停止してから `.states/http_cache`、`.states/yfinance_cache`、`.states/market_context_cache`、`.states/option_chain_cache`、`.states/analysis_jobs` を削除してください。`.states` 全体を削除すると pytest/ruff の作業キャッシュも消えますが、次回実行時に再作成されます。

Reflex のフロントエンド検証では、Codex アプリの WindowsApps 配下にある `node.EXE` が `WinError 5` で実行できないことがあります。`rxconfig.py` は、存在する場合に `C:\Users\<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin` をPATH先頭へ入れ、実行可能な同梱Nodeを優先します。

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt -c constraints.txt
```

削除前に、ローカルだけで必要な仮想環境内ファイルがないことを確認してください。
