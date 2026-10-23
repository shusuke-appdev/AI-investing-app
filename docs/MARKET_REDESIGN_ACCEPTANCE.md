# 市場再構成・共通基盤の受入記録

2026-10-11追記：表示は [投資リサーチUI再設計](RESEARCH_UI_REDESIGN.md) で更新済み。以下の2026-10-09記録は取得・計算の受入履歴です。新UIは総覧を2指数チャート＋市場位置＋一体のTop5に整理し、方針は「確認事項」、データ状況は「データ」へ改称。未保存銘柄の主導線はCodexへの依頼文に変更し、CLIは操作説明へ移しました。取得プロフィールと計算定義は維持しています。

実施日: 2026-10-09。対象はローカルCodex版の市場再構成とF1–F8の共有修正。Reflex画面の再設計、本番停止、公開、commit/push/deploy、売買、課金は実施していません。先行調査は [MARKET_ANALYSIS_REDESIGN.md](MARKET_ANALYSIS_REDESIGN.md)、利用手順は [CODEX_RESEARCH.md](CODEX_RESEARCH.md)。

## 実装と判断材料

新規取得の既定はstandard。29項目を全部取得して隠す方式ではなく、共有する価格・金利・信用・予定から必要な観測だけを計算します。5つの問いと反証を初期表示し、出典・内訳・旧方式だけを展開します。Pythonが観測・関係・条件付き解釈を生成し、JavaScriptは表示します。方針は市場と同じ接続オブジェクトを参照し、別の結論や配分を計算しません。

テーマは5/21/126営業日ごとに構成銘柄中央値の市場相対騰落（差、pp）で順位付けし、取得率60%以上かつmin(3,登録数)を要求。初期値6か月。登録順の代表3銘柄を同じ行に常時表示し、テーマ名の直下で全代表の同期間値を比較できます。未保存銘柄は銘柄名を表示した「未保存」を開くと具体的なCodex依頼とコマンドが現れます。旧20営業日値を21/126へ読み替えません。

総覧の配置は維持。標準Top5と棒グラフは6か月の新順位・同じ5テーマに変更し名称を明示。これは意図した変更で、旧複合点の順位を同じ方式だと見せません。旧総合順位は元スナップショットの日付付き研究参考として保存・表示します。

## 29項目の対応表

「研究詳細」は市場画面の展開先であり、保存済みの場合に閲覧できます。更新は`--profile advanced`または従来の明示stage refresh。standardで更新しない結果は元の日付と「今回の対象外」を保ち、失敗時の前回値・適用対象外と区別します。未取得を取得済みとしません。

|旧項目（catalog.pyのキー）|standardの利用先／代替|旧方式の扱い|
|---|---|---|
|market_data|①②④の指数・金利・信用・為替・原油観測|全資産一覧は研究詳細|
|market_charts|総覧の2系列・共通日比較|専門履歴は研究詳細|
|evaluation|①⑤の観測・条件付き解釈、総合点なし|研究詳細|
|ibd_regime|①の50/200日線・限定母集団と区別|IBD代理判定は研究詳細|
|regime_playbook|⑤と方針の反証・次の確認|旧研究姿勢は研究詳細|
|microstructure|①の参加代理、実流動性と区別|研究詳細。JPのUS専用監視は適用対象外|
|momentum|③・テーマの1週/1か月/6か月|旧方式は研究詳細|
|monitor|②の価格位置・出来高|US専用売り抜け等は研究詳細・JP主分析から除外|
|market_distortions|②の20日線乖離|旧歪み判定は研究詳細|
|trend_ranking|③・テーマ・総覧の期間別中央値相対順位|旧総合順位を別の研究参考へ保持|
|opportunity_themes|③の相対順位と取得率|旧候補判定は研究詳細。代表＝財務確認済みではない|
|important_levels|②の20観測高安・終値|支持抵抗・価格帯出来高は研究詳細|
|market_timeframes|①②⑤で時間軸を分ける|旧将来見通しは研究詳細|
|strategy_regime|⑤と同じ根拠の方針|旧配分・姿勢は研究詳細|
|market_driver_monitor|④の水準%・変化bp、為替・原油|旧ドライバーは研究詳細|
|japan_conditions|JP①②④⑤、日本10年・現物需給|旧条件判定は研究詳細|
|sector_flow|③の相対騰落・取得率、純流入額と区別|旧価格出来高代理は研究詳細|
|credit_stress|④HY OAS、⑤共通窓の価格・信用|旧信用パネルは研究詳細|
|flow_monitor|①RSP/SPY・IWM/SPYの比率変化|旧ETF監視は研究詳細|
|flow_alignment|⑤で対象・期間・日付・親入力を照合|旧判定も存在だけで整合としない|
|cross_market|総覧2市場。欠測の比較は未確認|研究詳細、片市場を0補完しない|
|volatility_regime|④VIX、⑤信用との不一致|旧レジームは研究詳細・US参考を明示|
|vix_sq_alert|標準では計算しない|advanced、JPではUS参考|
|sentiment|標準では独立心理判定を作らない|advanced|
|short_horizon_forecast|標準では予測を計算しない|advanced、F7修正前のモデル結果は旧方式|
|composite_sentiment|標準では複合心理を計算しない|advanced|
|top_risk_signposts|⑤の反証・無効化・次の確認|旧兆候の集約は研究詳細|
|fomo_scan|標準では計算しない|advancedでも別の明示指定が必要|
|options|標準では取得しない|advancedでも別の明示許可が必要|

## F1–F8の回帰

主な固定入力テストは [test_market_standard.py](../tests/test_market_standard.py)。従来サービスの既存テストも維持し、意図した単位・JP対象・来歴の変更だけ期待値を更新しています。

|修正|実装・受入内容|
|---|---|
|F1|米金利FRED公表値を%のまま、水準差×100をbp。負値・0も許容し倍率推測なし。4.25−0=425bpを固定検査|
|F2|非数値・非有限・非正価格・日付順序・急な価格比・終値と高安の不整合を検出。事前のok属性で再検査を迂回できない。MA/支持抵抗/主条件へ不整合履歴を渡さない|
|F3|取得元・元の取得日時・観測日・品質・キャッシュ・失敗を保存まで保持。履歴切出しもattrs保持。メモリhitはコピーにmemory状態を付け、古い/失敗状態は昇格させない。計算日時はcalculated_atとして分離。来歴なしはunknownで最新扱いしない|
|F4|JPのUS専用microstructure/monitorを主分析から除外。米信用・VIX等は米国参考／外部環境参考|
|F5|存在、0補完、文字列、bool、日付不一致では整合にしない。対象・期間・始終日・方向・親入力を照合。株価と信用／VIXは別の共通21観測窓を保存し、最新公表日を改変しない|
|F6|一意な一時ファイル＋原子的置換、共有provider状態更新をロック。50並行保存と旧キャッシュ互換を検査|
|F7|元の学習行位置+予測期間5が検証開始行より厳密に前。欠測除去後の位置を使う境界混入を回帰検査。旧モデル検証を新方式としない、任意MLを新規導入しない|
|F8|stage契約と依存注入を分離。facade/workflow両方のimport順を新しいPythonプロセスで検査|

接続7ケースは指数上昇と参加劣後、中期と短期の逆向き、株価と信用、VIXと信用の不一致、名目と実質金利、為替と原油、テーマ内部。固定入力で「支える／弱める／時間軸が異なる／参考／比較不能」と反証・無効化・次の確認を検査。一括の強気／弱気・確率へ潰さず、同じ価格・VIXを独立した複数の裏付けとして数えません。JP限定母集団の200日線上比率は水準で、6か月騰落方向の裏付けにはしません。

## 実データ・非取得の正常な結果

CLI実データ更新は`021c91a1-9c32-4e91-bdcb-e1b56220da6a`、更新ボタンの実行は`27f1d965-1ae6-442c-a537-f7051ef06e03`。最後の日本向け確認先文言修正を含む標準更新は`333a8a15-da5f-467b-b051-e3b08f9164b5`、snapshot v2。取得→検査→計算→保存→再読込、日米の方針との同一根拠、6社の保持を [snapshot-audit.json](../.states/market_redesign_acceptance/snapshot-audit.json)、[UI更新照合](../.states/market_redesign_acceptance/ui-snapshot-audit.json)、[最終照合](../.states/market_redesign_acceptance/final-snapshot-audit.json) に記録。

|対象|確認結果／影響|
|---|---|
|共有価格|登録テーマ全体を含む445系列を一意化。standardの旧4stage/ML/options/FOMO/企業原資料への非呼出を固定入力で監視|
|米国|76テーマ、6か月の有効順位76。最終77観測中65 available、12 unavailable。初回CLIは79観測中69/10。再取得による品質変化を隠さず欠測は0補完しない|
|日本|34テーマ。1306.Tの価格基準不連続で市場相対順位は全34テーマ確認待ち。最終55観測中33 available、22 unavailable（初回57観測中37/20）。ETF価格をTOPIX指数値とせず、倍率修復・別系列の無断接合をしない|
|USD/JPY|取得履歴の終値と高安値が整合しないため10派生観測を両市場で停止。原因の断定や値の自動補正をせず、為替×原油接続は比較不能|
|VIX・個別価格の再取得|UI再取得でVIXの終値と高安の不整合を検出し、水準・変化とVIX×信用の関連比較を停止。両市場にUS参考の未確認理由を表示。Yahoo取得中のCRSP/7270.TはSQLite lockエラーで欠測、テーマの同期間取得率に反映。取得成功・全件完備とはしない|
|米金利・信用|[FRED DGS10](https://fred.stlouisfed.org/series/DGS10)5.28%、DGS2、DFII10実質2.92%、HY OAS3.09%。観測日10/07。各水準・bp変化・共通日比較を保存。系列の公表単位と出典を保持|
|日本10年|[財務省当月CSV](https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv)と[過去CSV](https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv)を照合。10/08=3.089%、21観測のbp変化あり。重複日は当月版を優先し両出典・取得日時を記録|
|公式会合|[Fed](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)次回10/28、[日銀](https://www.boj.or.jp/mopo/mpmsche_minu/index.htm)次回10/30を保存。14日外でも次回会合を表示。確認できない時刻は時刻未定|
|BLS|[2026公式予定](https://www.bls.gov/schedule/2026/home.htm)はローカル取得でHTTP403。理由付き未取得、予定や市場予想値を捏造しない。DSTは固定公式形式入力でAmerica/New_York→UTCを検証|
|JPX現物海外投資家|[公表元](https://www.jpx.co.jp/markets/statistics-equities/investor-type/index.html)と[利用条件](https://www.jpx.co.jp/term-of-use/index.html)を確認。二次利用許諾を確認できないため自動収集せず理由付き未取得。実数の最新週・4週集計のライブ成功とは報告しない|

JPXは確認済みの正規化入力だけに対応します。新旧原表の金額列・対象・区分・千円等の単位・訂正箇所を人が確認し、円へ換算した値、資料箇所、確認日、実際の許諾根拠を保存します。自動Excel解析を実装・ライブ検証したという意味ではありません。先物・株数・貸借残高と合算しません。固定入力で金額0/負値、単位違い拒否、非重複かつ連続4週、欠週停止、14日超の古さ、元の確認日の保持、入力→保存→再読込を確認。許諾未確認の実数収集は行っていません。

6社（AAPL/7203.T/JPM/8306.T/PLD/8951.T）の主条件・分析・原資料・複数評価は元snapshotとのフィールドハッシュ比較で一致。企業資料の確認日は更新しません。AAPLのDCF/SOTP、JPM残余利益、PLD REIT方式、日本3社の根拠付き算定不能を含め既存表示を回帰。今回、新しい企業会計照合を行ったとは報告しません。

## 操作・画面・互換

ブラウザ受入記録は [.states/market_redesign_acceptance/browser-acceptance.json](../.states/market_redesign_acceptance/browser-acceptance.json)。6画面×日米×明暗×320/736/1024/1440×高さ1000/1440=192条件を修正後と最終UI更新後にも検査。最後の日本向け次の確認先の修正後、変更3画面の96条件も再検査。画面全体の横はみ出しなし、モバイル方針ナビ45px・ボタン44pxで縦伸びなし。広い表は内部スクロール。重要数値・反証は初期表示。プレビューのviewportは検査後に通常サイズへ復帰。

- テーマ54条件（3期間×3方向×3順位×日米）を操作し、表示された数値で昇降順・方向・取得率順を検査。検索、Enter展開、全代表比較、保存済みAAPLへの移動、未保存の具体的依頼を確認。
- 保存6社×5期間×線形/対数=60チャート条件。凡例、全価格offでも出来高保持、全系列off、日付キー操作、会計・複数評価・資料リンクを確認。
- v1/v2複数読込、不正ファイルを含む読込の原子的拒否と既存画面保持、負値・0・欠損の区別を確認。元ファイルは書き換えない。
- 所有する8768プレビューだけを停止し、読込済み全6画面をオフライン操作。接続失敗を表示して保存画面は保持。その後サーバーを復帰。ネットワーク／セキュリティ設定は変更しない。
- iframe検査中、出典URLのない過去のMutationObserver警告1件を記録。アプリのコードに同APIがなく操作は継続できたため、検査側の可能性と切り分け、アプリ由来と断定していない。ブラウザファイル選択1回に285秒の実行待ちが生じたが、完了後の読込結果は確認済み。

画像: [市場](../.states/market_redesign_acceptance/market-final.jpg)、[テーマ](../.states/market_redesign_acceptance/theme-final.jpg)、[モバイル方針](../.states/market_redesign_acceptance/policy-mobile-final.jpg)。

## 時間・呼出回数

測定記録は [benchmark-standard.json](../.states/market_redesign_acceptance/benchmark-standard.json) と [benchmark-advanced.json](../.states/market_redesign_acceptance/benchmark-advanced.json)。同じ日米対象、オプション/FOMO/モデルAPI/個別企業資料は指定せず測定。HTTPはホストごとの件数だけ記録し、URL引数・認証ヘッダーを保存しません。

|方式|新プロセス・既存永続キャッシュあり|同プロセス再実行|HTTP件数 初回/再実行|
|---|---:|---:|---:|
|standard|22.080秒|2.747秒|893 / 1|
|advanced（旧方式）|46.139秒|15.239秒|1260 / 302|

空キャッシュからのcold測定ではありません。キャッシュは削除せず、初回価格はlive、再実行は保存価格を利用。BLS失敗は再試行1件、旧stageの背景要求・タイムアウト・測定後の細部修正の影響もあります。この一回の条件下の結果であり一般的な速度保証にはしません。445銘柄の一意化はYahoo内部HTTPを1件にする意味ではありません。

## 再現と標準ゲート

```powershell
# 通常運用（ボタンも同じstandard経路）
.venv\Scripts\python.exe scripts\research.py update --open
# 旧分析の明示更新。オプション/FOMOは別指定
.venv\Scripts\python.exe scripts\research.py market --market JP --profile advanced
# 保存・銘柄保持・方針同一性の検査
.venv\Scripts\python.exe scripts\market_redesign_acceptance.py .states\research_runs\a4355623-3c00-4201-ba95-f81a4f6051e8\research.json .states\research_runs\021c91a1-9c32-4e91-bdcb-e1b56220da6a\research.json --output .states\market_redesign_acceptance\snapshot-audit.json
# 再取得を伴う任意の測定。通常運用には不要
.venv\Scripts\python.exe scripts\market_profile_benchmark.py --live --profile standard --output .states\market_redesign_acceptance\benchmark-standard.json
# 標準検証
.venv\Scripts\python.exe scripts\check.py --coverage
```

最終標準ゲートは556テスト、71.47% branch coverage、依存整合・compile・Ruff lint/format・mypy・Reflex production export・9route静的意味検査が合格（全再実行、exit0）。通常sandboxでGit/MSYSのローカルbareリポジトリ操作・CIM・Bunが失敗したため、同じゲートを承認済み通常実行で再試行。テストや閾値を弱めていません。最後の日本向け文言修正のテストでUS代理を残した固定入力の誤りを修正し、全ゲートも再検査。両Skillsのquick_validateも合格。progress.mdに最終close-outを記録。

復帰経路: advanced明示更新、日付を保持した旧保存の読込、稼働を維持したReflex/HF。追加許諾が必要なJPX、取得拒否されたBLS、不整合価格の関連結果を成功として扱わず、確認経路と影響を表示します。
