# 運用・環境設定ガイド

## 必須ランタイム

- Python 3.12 推奨
- PowerShell または互換シェル
- Docker を使う場合は Docker Desktop

## 環境変数

| 変数 | 必須度 | 用途 |
| --- | --- | --- |
| `GEMINI_API_KEY` | AI機能には必須 | Gemini による市況・銘柄・ポートフォリオ分析 |
| `GEMINI_MODEL_NAME` / `GEMINI_MODEL` | 任意 | Geminiモデル名の上書き。未設定時は `gemini-3.7-flash` |
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
| `PRIVATE_DEPLOYMENT_ACK` | Private Spaceでは必須 | Space が Private であることを確認した後にだけ `1` を設定する起動ガード確認値 |

## ローカル起動

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install pip==25.3 setuptools==82.0.1 wheel==0.48.0
python -m pip install -r requirements-lock.txt
reflex run
```

## Docker起動

```powershell
docker build -t ai-investing-app .
docker run --env-file .env -p 7860:7860 ai-investing-app
```

Dockerfile は Hugging Face Spaces の7860番ポートを前提にし、依存ビルドと実行環境を分離した非rootコンテナです。ローカル保存を使う場合は `/app/data`、Reflex状態は `/app/.reflex_states`、アプリキャッシュは `/app/.states` を書込可能な永続領域として扱ってください。
アプリは個人利用の単一モードです。ローカルでは追加設定なしで全機能を利用できます。Hugging Face Spaces では Space を Private に変更し、Private 表示を確認してからだけ `PRIVATE_DEPLOYMENT_ACK=1` を追加してください。Public のまま ACK だけを追加して起動ガードを回避してはいけません。`SPACE_ID` がある環境で確認値がない場合は起動を拒否します。

## Hugging Face Spaces 復旧・デプロイ順序

1. Space を Private にし、Hub API でも `private: true` を確認する。
2. Supabase project が `INACTIVE` なら復元し、`COMING_UP` / `RESTORING` を待って `ACTIVE_HEALTHY` になるまで 521 や接続失敗をアプリ障害として扱わない。
3. 同一 project ref のローカル `SUPABASE_SECRET_KEY` で `scripts/live_smoke.py --require-supabase` を実行し、`user_settings` の一時 insert/select/delete と後片付けを通す。
4. 値をログへ出さず、Space secret に `SUPABASE_SECRET_KEY` を登録する。Private 表示を再確認してから variable `PRIVATE_DEPLOYMENT_ACK=1` を登録する。
5. main を push し、CI が今回作成した Hugging Face deploy commit SHA、Hub の現在 SHA、`RUNNING`、認証付き `/_health` の HTTP 200 と正常 JSON を同じ revision の証拠として確認する。
6. Private Space の主要画面とデータ品質、および新 secret での Supabase CRUD を確認してから、互換用 `SUPABASE_KEY` を削除する。削除後の再起動も同じ revision-aware 検証で確認する。

内部検証器は `HF_TOKEN` を環境変数からだけ読み、次の形で使用します。token や Supabase secret は引数やログへ渡しません。

```powershell
python scripts/verify_hf_deployment.py --space owner/name --expected-sha <sha> --health-url <url> --require-private --timeout-seconds 900
```

## 定期的な確認コマンド

```powershell
.\.venv\Scripts\python.exe scripts\check.py --quick
.\.venv\Scripts\python.exe scripts\check.py
.\.venv\Scripts\python.exe scripts\check.py --coverage
```

`--quick` はcompileall、Ruff、`integration` / `slow` 以外のpytestを実行します。引数なしはReflex exportと静的UI検査を含む完全ゲートです。`--coverage` は完全ゲートへbranch coverageを追加し、`.states/` に成果物を出します。初回はカバレッジ率で失敗させません。

2026-07-14の初回branch coverageは62.9%（`src` + `frontend`）です。HTMLとJSONは `.states/coverage_html/` と `.states/coverage.json` に生成されます。

同日の実測はquick 10.0-10.6秒、coverage完全ゲート55.5秒、引数なし完全ゲート33.2秒です。マシン・キャッシュ状態で変動します。

外部APIに依存する確認は失敗しやすいため、標準pytestでは明示的モックを使います。旧 `scripts/debug/`、`scripts/verify/`、個別のEDINET/options検証は廃止し、実API確認を `scripts/live_smoke.py` に集約しています。

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

Supabaseを必須にするには `--require-supabase` を付けます。`--require-optional` は後方互換のSupabase専用エイリアスで、予測など無関係なSKIPを失敗扱いしません。Finnhub、EDINET、yfinance optionsを必須にする場合は、それぞれ `--require-finnhub`、`--require-edinet`、`--require-yfinance-options` を使います。
MarketData.app の live オプション取得を必須検証にするには、`.env` に `MARKETDATA_TOKEN=<token>` と `MARKETDATA_OPTIONS_MODE=preferred` を設定したうえで、クレジット消費を明示承認する `--allow-marketdata-credits` と `--require-marketdata` の両方を付けます。承認フラグがなければtokenの有無にかかわらず通信せず `SKIP` とし、アプリ本体は yfinance/cache fallback で継続します。live smoke は 0DTE の時刻依存を避けるため、既定で `--marketdata-min-dte 1` の次回有効満期を確認し、追加で `--marketdata-horizon-dtes 7,30` の満期別チェーンも確認します。その後、`analyze_option_sentiment()` が current / 1W / 1M の `term_structure` を MarketData.app 系 source で組み立て、各期限の`skew_detail`にmethod、Put/Call両脚、流動性、as-ofがあることまで確認します。

```powershell
.\.venv\Scripts\python.exe scripts\live_smoke.py --allow-marketdata-credits --require-marketdata --marketdata-tickers SPY --marketdata-min-dte 1 --marketdata-horizon-dtes 7,30
```

MarketData.app smoke の `calls=100/100`、`puts=100/100` は `strikeLimit=100` の片側取得上限に到達したという意味で、完全チェーン件数ではありません。IVやDTEを読むときは同じ行の `as_of` を確認してください。週末・祝日・休場日前後は、APIのlive応答でも最終取引日時点の `updated` に基づく値になることがあります。

2026-06-12時点の本番確認:

- SPY/yfinance、AAPL/Finnhub、ホスト配置ガードとHTTP 200本番起動は実スモークで確認します
- FRED公式CSVは一時的な504/タイムアウト時もあり、その場合は信用ストレス分析がキャッシュ・代替経路で継続することを確認
- Supabase本番プロジェクトは4テーブルのinsert/select/update/deleteをロールバック付きで通過

### Supabase

`SUPABASE_URL` と `SUPABASE_SECRET_KEY` を設定すると Supabase に保存できます。旧設定との互換のため `SUPABASE_SERVICE_ROLE_KEY` と `SUPABASE_KEY` も読みますが、新規環境では secret key をサーバー環境変数として使います。現在のコードは `portfolios`、`knowledge_items`、`user_settings`、`trade_plans` テーブルを前提にしています。

project 復元直後は `COMING_UP` / `RESTORING` や一時的な HTTP 521 が発生し得ます。`ACTIVE_HEALTHY` を確認してから credentialed smoke を行い、新しい `SUPABASE_SECRET_KEY` と旧 `SUPABASE_KEY` を同時に置く移行期間では新キーが優先されます。旧キーは新キーによる本番 CRUD と再起動が成功した後にだけ削除します。

Supabase の 2026-05-30 / 2026-10-30 の Data API 既定変更に対応するため、新規 Supabase プロジェクトまたは新規テーブル作成時は、データ移行前に [supabase/public_tables.sql](../supabase/public_tables.sql) を Supabase SQL Editor で実行してください。移行ツールからも同じ SQL を表示できます。この SQL は `postgres` ロールが今後作る `public` オブジェクトの自動 Data API 公開も抑止します。

```powershell
python tools/migrate_to_supabase.py --print-setup-sql
```

詳細は [Supabase Data API grants 対応](SUPABASE_DATA_API_GRANTS.md) を参照してください。

## 運用上の注意

- Portfolio・Knowledge、AI生成、URL・YouTube取り込みは単一の個人モードで利用できます。外部ホストではアクセス制御確認値が必須です
- 外部APIの制限により、オプション分析とニュース集約は一時的に空になることがあります
- Market Watch の詳細更新とStockの補助診断は、外部取得や重い計算が所定時間を超えた場合、その項目だけを `partial` / `failed` として扱い、取得済みの基本情報を表示します。失敗理由は各画面のデータ状態と「データ品質」ページの provider health で確認します
- 市場指数・セクター等の取得失敗は価格 `0.0` として表示せず、その項目を利用不可として省略します
- 総合テーマ順位は、2年監査を通した版管理済み代表銘柄、ETF proxy、市場benchmarkを1回で取得し、原則3銘柄以上かつ取得率60%以上のテーマだけを採点します。代表監査が未通過・証拠不足なら全構成銘柄を維持し、欠損は0点化しません。12時間の永続キャッシュを再利用します
- `/theme-leaders`は表示だけでは外部分析を開始しません。「候補探索を実行」でGemini探索最大1回、候補OHLCV一括1回、テクニカル通過後の企業情報最大15件を取得します。Gemini探索・深掘りは24時間cacheで、APIキー未設定・検索失敗時も登録代表銘柄だけで継続します
- 日本株の汎用現在値・価格履歴はyfinanceを使います。J-Quants Freeの価格系列は遅延するため現在値として扱わず、企業マスター・財務情報の補完に限定します
- 市場監視の起動時は前回の完全コンテキストを即時表示し、主要指数と市場姿勢・資金フロー・上位5テーマだけを更新します。全構成銘柄の取得は「トレンド/テーマ」を開いた場合だけ実行します
- 「詳細をすべて更新」では共有価格履歴を1回だけ取得し、信用/歪みとオプションを同時開始します。担当フィールドを統合した後、最新の信用・オプションでボラティリティ、センチメント、予測、戦略を再計算します。一方が失敗しても他方と既存概要を維持します
- 段階状態、所要時間、cache、警告、来歴はサイドバー最下部の「データ品質」に集約します
- IBD式市場状態は無料データによる近似です。公式IBD Market Pulseではなく、SPY / Nasdaq 100 の売り抜け日、ラリー試行、FTD、移動平均割れから分類します
- 「詳細更新」では、ETFリーダーシップproxyを市場全体の確認、選択市場ごとのセクター/テーマ資金流入判定を具体候補の抽出として扱います。US表示では日本株テーマを混ぜず、JP表示では日本株条件を扱います。これは売買命令ではなく、市場分析の入力です
- Market概要の株式指数・金利、商品、FX、暗号資産はUS/JPで同じ構成です。JPのセクター指数だけは、野村アセットマネジメントのNEXT FUNDS TOPIX-17 ETF（1617.T〜1633.T）を価格proxyとして表示します
- 日経平均上昇の6条件は、無料で自動取得できるデータを優先し、直接データがない条件は `データ不足` または `代理達成/代理未達` として表示します。上記の任意環境変数を設定すると、一部条件を直接値として評価できます
- 個別日本株の「需給期日」カードは4桁コードを自動で `.T` へ正規化し、制度信用の買い残・売り残を使える場合だけ信用倍率を判定します。データがない場合は `0` や中立値を入れず、`データ不足` としてAI入力にも渡します。一般信用込みの信用倍率はこの戦略の直接入力として扱いません
- 米国市場の VIX×SQ週アラートは、既存のCBOE VIX履歴取得を使い、MACDとパラボリックSARの同方向転換、および米国月次オプションSQ週への残存を研究用シグナルとして表示します。CBOE履歴がない、または60営業日未満の場合は未取得/データ不足として扱います
- yfinanceオプションデータにGreeks/Gammaがない場合、GEXは非表示になります。UIの `data_quality` バッジと品質警告を確認してください
- MarketData.appは `/market-watch` の明示的なOptions更新、統合トレンドランキングのテーマETFオプション更新、個別銘柄分析の所属テーマETFオプション確認時に利用します。起動時・単なる描画時・市場マイクロストラクチャー更新からは呼び出さず、APIクレジット消費を抑えます
- 標準運用は `MARKETDATA_OPTIONS_MODE=preferred` です。MarketData.appを優先し、204 no data、認証/HTTP/API失敗、必須列不足、トークン未設定時だけyfinance/cacheへ戻します。トークン未設定のローカル環境は「MarketData未設定」として扱い、アプリ全体の失敗にはしません
- `MARKETDATA_OPTIONS_MODE=shadow` は比較検証用として残します。画面表示と分析は従来のyfinance結果を維持し、MarketData.appの取得可否・基準時刻・契約既定mode・クレジット情報を品質警告へ記録します
- MarketData.app経路では満期一覧を確認し、米国東部時間の同日満期が有効な時間帯だけ0DTEを使い、引け後・週末・live smokeでは次回有効満期へ切り替えます。1W / 1M は `target_dte` に最も近い有効満期を選び、yfinance fallbackも同じ満期選択を使います。`strikeLimit=100`、標準契約、必要列だけを取得します。GEXのCall正・Put負は実ディーラー建玉を直接観測したものではなく、簡易な符号仮定です
- Market Watch のオプション分析は current / 1W / 1M の期間別行を表示し、`market_timeframes`も同じ`OptionContext.horizons`を参照します。IVスキューは流動性合格25Δ Put IV − Call IVを正本とし、10% OTM/yfinance/旧cacheは表示専用proxyです。SPY/QQQ/IWMを平均せず、freshなSPY直接値だけを市場方向の下方向警戒へ使います。これは価格予測の断定ではなく、オプション市場が織り込む想定変動幅・歪みの入力です
- MarketData.appの鮮度modeはAPIへ強制指定せず、アカウント契約の既定値を使います。リアルタイムとは断定せず、各カードの`updated`由来の基準時刻を確認してください
- データ信頼度・来歴は通常分析画面の上部には常時出さず、サイドバー/モバイルドロワー最下部の「データ品質」ページでProvider設定、最後の成功状態、失敗理由、stale cache/proxy/unavailableを集約確認します
- キャッシュ由来のデータは `source`、`fetched_at`、`is_stale`、`cache_status`、`quality_warnings` としてUI/AIへ渡します。`stale_cache` 表示がある場合は、外部API失敗時に最後の成功データを使っています
- 時系列データを突合する場合は `src/services/temporal_alignment.py` の as-of join を使い、許容時間差外の未突合行を `DataResult.is_partial` と `quality_warnings` で明示します
- 重い分析処理は `src/services/analysis_jobs.py` の `queued/running/succeeded/failed/partial/cancelled` 状態で管理し、単一Reflex環境ではローカルJSON永続化を使います
- 個別株分析は `StockAnalysisInputs` が同一実行内の価格・企業情報・ニュース・ベンチマーク取得を共有します。通常UIでは独立Trading Planページを使わず、Stock画面の「トレード分析」ボタンで既存分析結果から重要水準、タイミング、無効化条件、需給根拠を展開します
- Stockの主要な独立診断は最大4並列、各8秒・グループ16秒上限です。タイムアウトした診断だけを`partial`にし、企業情報・価格・他診断は維持します。類似局面0件やvol欠損を数値0として表示しません
- Portfolioは現地通貨時価を保持し、USD/JPYを確認できた場合だけ円換算総額・構成比を表示します。為替取得に失敗した場合はUSD/JPYを固定値で補わず、JPY・USD等の通貨別小計のみを表示します
- `yfinance` など外部データソースのレスポンススキーマは変更されることがあり、列名の変化に備えたテストが必要です
- AIレポートは入力データに依存するため、データ取得失敗時にはレポート品質も低下します
- Entry Frameworkは日足データによるproxyです。LoD、ORH、寄付き後30分、1-2時間確認、即時ギャップ抵抗は判定しません
- `.env`、SQLiteキャッシュ、アップロードファイル、生成zipは原則としてGit管理しません
- GitHub Actions の Hugging Face Spaces 同期は `main` / `master` へのpushをブランチ単位で直列化し、古い実行をキャンセルしてからforce pushします。push前に token と Private 状態を Hub API で検査します。push時に作成した deploy commit SHA をstep outputとartifactへ保存し、Hubの現在SHAとの一致、対象revisionの`RUNNING`、認証付き`/_health`のHTTP 200と`status=true`を最大15分確認します。旧revisionの200は合格にならず、対象revisionの`RUNTIME_ERROR`は安全な要約を残して即時失敗します。対象はGitHub Environment `hugging-face-production` の `HF_SPACE_REPO`、確認URLは `HF_SPACE_HEALTH_URL` で上書きできます
- quality jobはHugging Face同期より前にDockerイメージを実ビルドし、ローカル相当の単一モードで非rootコンテナを起動してReflex `/_health` のJSON `status=true`まで確認します。コンテナが早期終了した場合はログを出してdeployを止めます
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

米国市場の短期予測と複合センチメントを実データで検証する場合は次を使います。追加APIキーは不要です。Cboe、CFTC、OCCはいずれも公式公開データを使い、Gammaだけは既存の `MARKETDATA_TOKEN` があり直接かつ完全なチェーンを取得できた場合に有効化します。

```powershell
.\.venv\Scripts\python.exe scripts\backfill_market_sentiment.py --symbols SPY,QQQ --sessions 252
.\.venv\Scripts\python.exe scripts\live_smoke.py --require-market-forecast
```

OCC backfillは再開可能で、既取得日は再取得しません。60営業日未満はPut/Call percentileを算出せず、複合ルールをpartialとして表示します。短期予測は1・5・20営業日を個別にOOS判定し、`research_only` はUI/AIへの参考表示に限定されます。

`pytest` のキャッシュは、アクセス拒否が発生していた `.pytest_cache` ではなく `.states/pytest_cache` を使うように設定済みです。
`ruff` のキャッシュも `.states/ruff_cache` を使います。

Codex から一括検証する場合は、このリポジトリを workspace root として開いたスレッドで
`.venv\Scripts\python.exe scripts\check.py` を実行します。このスクリプトは依存関係を
自動インストールせず、コードも自動修正しません。別 workspace から実行したときの
temp/cache/`.web` 書き込み拒否は、まず sandbox 境界として切り分けます。

テストの分類、信頼度、データの現実性、限界、実行プロファイルは `tests/test_inventory.toml` が正本です。予測モデルのテストは時点整合・OOS評価・配線を検証しますが、実運用上の投資成果を保証しません。

ローカルキャッシュを初期化したい場合は、アプリを停止してから `.states/http_cache`、`.states/yfinance_cache`、`.states/market_context_cache`、`.states/theme_rankings`、`.states/theme_leader_discovery`、`.states/option_chain_cache`、`.states/marketdata_option_chain_cache`、`.states/analysis_jobs` を削除してください。`.states` 全体を削除すると pytest/ruff の作業キャッシュも消えますが、次回実行時に再作成されます。Reflexセッション状態だけを初期化する場合は `.reflex_states/` を削除します。

Reflex のフロントエンド検証では、Codex アプリの WindowsApps 配下にある `node.EXE` が `WinError 5` で実行できないことがあります。`rxconfig.py` は、存在する場合に `C:\Users\<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin` をPATH先頭へ入れ、実行可能な同梱Nodeを優先します。

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install pip==25.3 setuptools==82.0.1 wheel==0.48.0
python -m pip install --no-cache-dir -r requirements-lock.txt
```

削除前に、ローカルだけで必要な仮想環境内ファイルがないことを確認してください。
