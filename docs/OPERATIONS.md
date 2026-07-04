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
| `MARKETDATA_TOKEN` | 米国オプション分析に推奨 | MarketData.appのSPY / QQQ / IWMおよび主要テーマETF proxyのオプションチェーン、IV、Greeks、OI、Volume |
| `MARKETDATA_OPTIONS_MODE` | 任意 | `off` / `shadow` / `preferred`。トークン設定済みの未設定時は`preferred`、トークン未設定時は`off` |
| `JQUANTS_API_KEY` | 日本株分析では任意 | 日本株の企業マスター・財務情報。Freeの遅延価格系列は汎用現在値・履歴に使わない |
| `EDINET_API_KEY` | 日本株財務では推奨 | EDINET からの財務情報取得 |
| `NIKKEI_JSF_SHORT_BALANCE_BILLION` | 任意 | 日経6条件の条件1を直接判定するための、日証金合計売り残（億円） |
| `NIKKEI_LEVERAGE_MARGIN_RATIO` | 任意 | 日経6条件の条件2を直接判定するための、日経レバ1570信用倍率 |
| `NIKKEI_FOREIGN_INVESTOR_NET_BUY_BILLION` | 任意 | 日経6条件の条件6を直接判定するための、海外投資家買越額（億円） |
| `JP_MARGIN_ROWS_<ticker>` | 日本株需給期日では任意 | 個別日本株の制度信用残高。例: `JP_MARGIN_ROWS_7203_T` に `[{"date":"2026-06-01","system_buy_balance":900000,"system_sell_balance":1000000}]` のJSON配列を設定 |
| `JP_LOAN_ALERT_<ticker>` | 日本株需給期日では任意 | 個別日本株の貸株注意喚起・逆日歩フラグ。例: `JP_LOAN_ALERT_7203_T=active` |
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
- Trading Plan互換データ: `data/trading_plans.json`
- 知識DB: `data/knowledge*.json` 系のローカルファイル
- HTTPキャッシュ: `.states/http_cache/app_cache.sqlite` など用途別SQLite
- yfinanceタイムゾーンキャッシュ: `.states/yfinance_cache/`
- 市場サマリーキャッシュ: `.states/market_context_cache/*.json`
- オプションチェーンキャッシュ: `.states/option_chain_cache/*.json`
- MarketData.appオプションチェーンキャッシュ: `.states/marketdata_option_chain_cache/*.json`
- 分析ジョブ状態: `.states/analysis_jobs/*.json`
- Reflexセッション状態: `.reflex_states/`。アプリのデータキャッシュ `.states/` とは分離する

### Live smoke

外部API、公開読み取り専用ガード、設定済みのSupabaseを実データで確認します。作成したSupabase検証行は削除されます。

```powershell
.\.venv\Scripts\python.exe scripts\live_smoke.py
```

任意保存先が未設定の場合も失敗にするには `--require-optional` を付けます。
MarketData.app の live オプション取得を必須検証にするには、`.env` に `MARKETDATA_TOKEN=<token>` と `MARKETDATA_OPTIONS_MODE=preferred` を設定したうえで `--require-marketdata` を付けます。token 未設定の状態は `SKIP` とし、アプリ本体は yfinance/cache fallback で継続します。live smoke は 0DTE の時刻依存を避けるため、既定で `--marketdata-min-dte 1` の次回有効満期を確認し、追加で `--marketdata-horizon-dtes 7,30` の満期別チェーンも確認します。その後、`analyze_option_sentiment()` が current / 1W / 1M の `term_structure` を MarketData.app 系 source で組み立てたことまで検証します。

```powershell
.\.venv\Scripts\python.exe scripts\live_smoke.py --require-marketdata --marketdata-tickers SPY --marketdata-min-dte 1 --marketdata-horizon-dtes 7,30
```

MarketData.app smoke の `calls=100/100`、`puts=100/100` は `strikeLimit=100` の片側取得上限に到達したという意味で、完全チェーン件数ではありません。IVやDTEを読むときは同じ行の `as_of` を確認してください。週末・祝日・休場日前後は、APIのlive応答でも最終取引日時点の `updated` に基づく値になることがあります。

2026-06-12時点の本番確認:

- SPY/yfinance、AAPL/Finnhub、`APP_MODE=public_readonly` の書き込み防止とHTTP 200本番起動は実スモーク通過
- FRED公式CSVは一時的な504/タイムアウト時もあり、その場合は信用ストレス分析がキャッシュ・代替経路で継続することを確認
- Supabase本番プロジェクトは4テーブルのinsert/select/update/deleteをロールバック付きで通過

### Supabase

`SUPABASE_URL` と `SUPABASE_SECRET_KEY` を設定すると Supabase に保存できます。旧設定との互換のため `SUPABASE_SERVICE_ROLE_KEY` と `SUPABASE_KEY` も読みますが、新規環境では secret key をサーバー環境変数として使います。現在のコードは `portfolios`、`knowledge_items`、`user_settings`、`trade_plans` テーブルを前提にしています。

Supabase の 2026-05-30 / 2026-10-30 の Data API 既定変更に対応するため、新規 Supabase プロジェクトまたは新規テーブル作成時は、データ移行前に [supabase/public_tables.sql](../supabase/public_tables.sql) を Supabase SQL Editor で実行してください。移行ツールからも同じ SQL を表示できます。この SQL は `postgres` ロールが今後作る `public` オブジェクトの自動 Data API 公開も抑止します。

```powershell
python tools/migrate_to_supabase.py --print-setup-sql
```

詳細は [Supabase Data API grants 対応](SUPABASE_DATA_API_GRANTS.md) を参照してください。

## 運用上の注意

- `APP_MODE=public_readonly` ではPortfolio・Knowledge・Trading Plan互換データの読み書き、AI生成、URL・YouTube取り込みを拒否します。個人機能のナビゲーションも表示しません
- 外部APIの制限により、オプション分析とニュース集約は一時的に空になることがあります
- Market Watch の詳細更新とStockの補助診断は、外部取得や重い計算が所定時間を超えた場合、その項目だけを `partial` / `failed` として扱い、取得済みの基本情報を表示します。失敗理由は各画面のデータ状態と「データ品質」ページの provider health で確認します
- 市場指数・セクター等の取得失敗は価格 `0.0` として表示せず、その項目を利用不可として省略します
- Theme Rankingは指定期間を満たす構成銘柄だけを使い、2銘柄以上かつ構成銘柄の40%以上を取得できたテーマだけを表示します
- 日本株の汎用現在値・価格履歴はyfinanceを使います。J-Quants Freeの価格系列は遅延するため現在値として扱わず、企業マスター・財務情報の補完に限定します
- Market Intelligence の起動時は軽量サマリーのみ自動取得します。詳細分析はサイドバーの「市場監視」で「詳細更新」を押すと、キャッシュ/サマリー、Theme/Flow、Vol/Sentiment、Credit/Risk、Optionsの順に段階取得します
- 「市場監視」には、IBD式市場状態、状態別プレイブック、総合市場監視、テーマモメンタム、テーマランキング、オプション分析、市場の歪み検知を統合しています。各段階は「取得中」「最新」「キャッシュ」「一部取得」「取得失敗」を表示します
- IBD式市場状態は無料データによる近似です。公式IBD Market Pulseではなく、SPY / Nasdaq 100 の売り抜け日、ラリー試行、FTD、移動平均割れから分類します
- Market Recap では「＋」ボタンから任意の追加分析項目を入力できます。入力内容はプロンプトに渡され、現在の市場状態、フロー、ファンダメンタル、反証条件に結び付けて分析されます
- 「詳細更新」では、ETFリーダーシップproxyを市場全体の確認、選択市場ごとのセクター/テーマ資金流入判定を具体候補の抽出として扱います。US表示では日本株テーマを混ぜず、JP表示では日本株条件を扱います。これは売買命令ではなく、市場分析の入力です
- Market概要の株式指数・金利、商品、FX、暗号資産はUS/JPで同じ構成です。JPのセクター指数だけは、野村アセットマネジメントのNEXT FUNDS TOPIX-17 ETF（1617.T〜1633.T）を価格proxyとして表示します
- 日経平均上昇の6条件は、無料で自動取得できるデータを優先し、直接データがない条件は `データ不足` または `代理達成/代理未達` として表示します。上記の任意環境変数を設定すると、一部条件を直接値として評価できます
- 個別日本株の「需給期日」カードは4桁コードを自動で `.T` へ正規化し、制度信用の買い残・売り残を使える場合だけ信用倍率を判定します。データがない場合は `0` や中立値を入れず、`データ不足` としてAI入力にも渡します。一般信用込みの信用倍率はこの戦略の直接入力として扱いません
- 米国市場の VIX×SQ週アラートは、既存のCBOE VIX履歴取得を使い、MACDとパラボリックSARの同方向転換、および米国月次オプションSQ週への残存を研究用シグナルとして表示します。CBOE履歴がない、または60営業日未満の場合は未取得/データ不足として扱います
- AI Market Recap は米国市場を主軸にし、日本市場は米国市場との相対強弱、日経6条件、ドル円・原油・資金流入の文脈で補助的に扱います
- yfinanceオプションデータにGreeks/Gammaがない場合、GEXは非表示になります。UIの `data_quality` バッジと品質警告を確認してください
- MarketData.appは `/market-watch` の明示的なOptions更新、統合トレンドランキングのテーマETFオプション更新、個別銘柄分析の所属テーマETFオプション確認時に利用します。起動時・単なる描画時・市場マイクロストラクチャー更新からは呼び出さず、APIクレジット消費を抑えます
- 標準運用は `MARKETDATA_OPTIONS_MODE=preferred` です。MarketData.appを優先し、204 no data、認証/HTTP/API失敗、必須列不足、トークン未設定時だけyfinance/cacheへ戻します。トークン未設定のローカル環境は「MarketData未設定」として扱い、アプリ全体の失敗にはしません
- `MARKETDATA_OPTIONS_MODE=shadow` は比較検証用として残します。画面表示と分析は従来のyfinance結果を維持し、MarketData.appの取得可否・基準時刻・契約既定mode・クレジット情報を品質警告へ記録します
- MarketData.app経路では満期一覧を確認し、米国東部時間の同日満期が有効な時間帯だけ0DTEを使い、引け後・週末・live smokeでは次回有効満期へ切り替えます。1W / 1M は `target_dte` に最も近い有効満期を選び、yfinance fallbackも同じ満期選択を使います。`strikeLimit=100`、標準契約、必要列だけを取得します。GEXのCall正・Put負は実ディーラー建玉を直接観測したものではなく、簡易な符号仮定です
- Market Watch のオプション分析は current / 1W / 1M の期間別行を表示し、AI Market Recap と `market_timeframes` も同じ `OptionContext.horizons` を参照します。これは価格予測の断定ではなく、オプション市場が織り込む想定変動幅・歪みの入力です
- MarketData.appの鮮度modeはAPIへ強制指定せず、アカウント契約の既定値を使います。リアルタイムとは断定せず、各カードの`updated`由来の基準時刻を確認してください
- データ信頼度・来歴は通常分析画面の上部には常時出さず、サイドバー/モバイルドロワー最下部の「データ品質」ページでProvider設定、最後の成功状態、失敗理由、stale cache/proxy/unavailableを集約確認します
- キャッシュ由来のデータは `source`、`fetched_at`、`is_stale`、`cache_status`、`quality_warnings` としてUI/AIへ渡します。`stale_cache` 表示がある場合は、外部API失敗時に最後の成功データを使っています
- 時系列データを突合する場合は `src/services/temporal_alignment.py` の as-of join を使い、許容時間差外の未突合行を `DataResult.is_partial` と `quality_warnings` で明示します
- 重い分析処理は `src/services/analysis_jobs.py` の `queued/running/succeeded/failed/partial/cancelled` 状態で管理し、単一Reflex環境ではローカルJSON永続化を使います
- 個別株分析は `StockAnalysisInputs` が同一実行内の価格・企業情報・ニュース・ベンチマーク取得を共有します。通常UIでは独立Trading Planページを使わず、Stock画面の「トレード分析」ボタンで既存分析結果から重要水準、タイミング、無効化条件、需給根拠を展開します
- `yfinance` など外部データソースのレスポンススキーマは変更されることがあり、列名の変化に備えたテストが必要です
- AIレポートは入力データに依存するため、データ取得失敗時にはレポート品質も低下します
- Entry Frameworkは日足データによるproxyです。LoD、ORH、寄付き後30分、1-2時間確認、即時ギャップ抵抗は判定しません
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

Codex から一括検証する場合は、このリポジトリを workspace root として開いたスレッドで
`.venv\Scripts\python.exe scripts\check.py` を実行します。このスクリプトは依存関係を
自動インストールせず、コードも自動修正しません。別 workspace から実行したときの
temp/cache/`.web` 書き込み拒否は、まず sandbox 境界として切り分けます。

ローカルキャッシュを初期化したい場合は、アプリを停止してから `.states/http_cache`、`.states/yfinance_cache`、`.states/market_context_cache`、`.states/option_chain_cache`、`.states/marketdata_option_chain_cache`、`.states/analysis_jobs` を削除してください。`.states` 全体を削除すると pytest/ruff の作業キャッシュも消えますが、次回実行時に再作成されます。Reflexセッション状態だけを初期化する場合は `.reflex_states/` を削除します。

Reflex のフロントエンド検証では、Codex アプリの WindowsApps 配下にある `node.EXE` が `WinError 5` で実行できないことがあります。`rxconfig.py` は、存在する場合に `C:\Users\<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin` をPATH先頭へ入れ、実行可能な同梱Nodeを優先します。

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt -c constraints.txt
```

削除前に、ローカルだけで必要な仮想環境内ファイルがないことを確認してください。
