# Codexローカル移行版: 実データ・受入記録

2026-10-09の市場再構成と保存済み6社の回帰確認は [市場再構成の受入記録](MARKET_REDESIGN_ACCEPTANCE.md)。以下の企業資料確認日は今回の市場更新で変更していません。

確認日: 2026-10-07。機能対応は [対応表](RESEARCH_FEATURE_PARITY.md)、通常操作は [操作説明](CODEX_RESEARCH.md)。これは研究システムの検証記録であり、投資推奨・将来利益の保証ではない。

## 6社の原資料照合

原数値、元単位、通貨、期間境界、会計基準、連結範囲、公開/確認日、表/ページ、source IDは `.states/reviewed_evidence_20261007.json` に保存。原文確認からの転記手順は `.states/build_reviewed_migration.py`、PDF・SHA256/取得記録は `.states/filing_documents/`。照合結果は `.states/migration_accounting_audit_20261007.json`。

|会社|対象の直近3年・最新公表期|事業・会計確認|確認状態|
|---|---|---|---|
|Apple AAPL|FY2023/24/25（9月期）、2026-06-27まで9か月|US GAAP連結、5報告地域セグメントと本社費用。製品別売上を別軸で二重計上しない。原CFと正規化FCFFを区別|基本/追加36確認項目、未調査0、原事実40|
|トヨタ 7203.T|FY2024/25/26（3月期）、2026-06-30 Q1|IFRS連結、自動車/金融/その他3と消去。貸付/リースを含む連結CFを自動車FCFFとしない。最新日野連結除外・取消株式の範囲|36確認項目、未調査0、原事実32|
|JPMorgan JPM|2023/24/25年、2026-06-30半年|US GAAP、親会社普通株利益/簿価/自己株控除後株数/ROEを統一。CCB/CIB/AWM＋Corporateから全社利益、普通株利益への帰属差を別記|20確認項目、未調査0、原事実16|
|三菱UFJ 8306.T|FY2024/25/26（3月期）、2026-06-30 Q1|JGAAP、親会社普通株簿価はNCI/新株予約権除外。8報告セグメントの名称変更と営業純益→経常利益調整。Q1 CF未作成を確認|20確認項目、未調査0、原事実16|
|Prologis PLD|2023/24/25年、2026-06-30半年|US GAAP、Real Estate/Strategic Capitalの2報告セグメント。FFO/modified/Core/AFFOの原表符号付き調整16表、普通株+OP+報酬希薄化分母|40確認項目、未調査0、原事実37|
|日本ビルファンド 8951.T|2023/24/25の各非重複2半期と最新2026-06-30半期|JGAAP単体、単一不動産賃貸を資料確認。FFO/AFFO調整20表。Core FFOは非開示、分配金とは別。2024-10の5:1分割と加重平均/期末投資口数を区別|100確認項目、未調査0、原事実100|

NBFの3つの「12か月」は暦年に対応する非重複半期合算TTMで、会社の年度決算という表示はしない。[会社の決算期間](https://www.nbf-m.com/nbf/ir/schedule.html)。残高を半期合算しない。TTMの構成原期間/source、重複/欠落/和を検査する。

訂正/最新版確認元: [Apple](https://investor.apple.com/sec-filings/)、[トヨタ](https://global.toyota/en/ir/financial-results/archives/03.html)、[JPM](https://jpmorganchaseco.gcs-web.com/ir/sec-other-filings/overview)、[MUFG](https://www.mufg.jp/ir/fs/2025/index.html)、[PLD](https://ir.prologis.com/financials/annual-reports)、[NBF](https://www.nbf-m.com/nbf/ir/index.html?cate=all&year=2026)。確認した一覧/訂正の内容と入力影響をamendmentsに保存し、一覧の確認日を原決算資料の公開日として使わない。

### 取得制約・非開示・算定しない理由

- JPMの過年度ARS/A登録を公式一覧で確認。旧ARS/A PDFは会社配信timeout/SEC403・サイズ制約により差分全量を取得できない。現在公開される年次原表/最新3年比較を採用し、旧版との差分全量確認済みとはしない。この取得不能経路と入力への影響を保存している。
- MUFGの補足資料p30の有価証券評価訂正、NBFの物件名称訂正/将来修繕計画訂正を確認。採用した普通株会計・実績調整への影響と最新版を記録。
- NBF Core FFOは独自のFFO/AFFOへの改名で補完しない。MUFG最新Q1 CFは未作成。会社が非開示/適用対象外の項目は0ではなく理由付き状態。
- トヨタの混在事業別倍率/EV・株式価値橋渡し、MUFGの将来持続ROE、NBFの将来倍率は、この確認資料から確定できる事実ではない。追加仮定がないため、この3社の全社価値は未算定と表示。会計確認完了と価値算定可能は別。

## 4方式の実資料例

|方式|実資料・入力・仮定|実装/受入|
|---|---|---|
|FCFF DCF|Apple FY2025。同年度EBIT、DA、設備支出、運転資本原項目を調整。税率21%・その他持続運転資本変動0は正規化仮定で、会社公表FCFFではない|5年/永久成長→EV→現金/負債/非事業資産/NCI→普通株。弱気/基本/強気、根拠/計算/価格日/評価期間、DCF限定逆算|
|SOTP|同じApple年度5全報告セグメント、全社EBITへ本社費用調整。倍率は仮定|全セグメント・本社費用・価値橋渡し完備後のみ全社値。同銘柄DCFと併存|
|残余利益|JPM FY2025親会社普通株利益/簿価/株数/ROE。持続ROE17%、資本コスト10%、成長2%は将来仮定|同帰属普通株簿価/株数へ超過収益を加算。預金の産業負債控除なし、現金/負債を必須にしない|
|FFO倍率|PLD FY2025 Core FFO原調整表、OP調整後分子5,562,332千USD/希薄化分母956,832千口。基本14倍は仮定（弱気10/強気18）|年度・同範囲分子分母。FFO/Core/AFFO/分配金を別ラベル。半年値に年度倍率を適用しない|

数値結果・全入力・3ケース・適用不能理由は最終runの `summary.md` と銘柄画面に保存。利息後CF、年度CF/最新中間BS混在、他社資料、未確認source、単位違い、文字列/bool/nonfinite、部分SOTP、セグメント二重/調整漏れ、TTM重複/欠落/合算不一致は算定停止をテスト。

## 再現手順

```powershell
# 通常の取得（オプション/モデル課金なし）
.venv\Scripts\python.exe scripts\research.py overview
.venv\Scripts\python.exe scripts\research.py stock --ticker AAPL
.venv\Scripts\python.exe scripts\research.py stock --market JP --ticker 7203.T
.venv\Scripts\python.exe scripts\research.py theme --market JP
# 今回の6社転記と固定保存入力の再計算・保存・再読込
.venv\Scripts\python.exe .states/build_reviewed_migration.py
.venv\Scripts\python.exe .states/build_final_migration.py
# 任意の新資料は標準CLIから追加
.venv\Scripts\python.exe scripts\research.py stock --resume <research.json> --evidence <reviewed.json>
.venv\Scripts\python.exe scripts\research.py overview --replay <research.json>
.venv\Scripts\python.exe scripts\check.py --coverage
```

転記スクリプトは新規公開資料を自動確認したことにはしない。保存原文/確認記録から同じ転記を再現する。新しい公表期を使う際は原文と訂正を改めて確認。`build_final_migration.py` は通信を禁止したresume、元ファイル/analysis不変、6社252価格行、全社会計audit、AAPL複数方式、6解釈、保存後schema再読込をassertする。

最終preview run: `.states/research_runs/a4355623-3c00-4201-ba95-f81a4f6051e8/`。実データ経路記録 `.states/migration_roundtrip_20261007.json` はpassed。元runは書き換えない。HTMLは自己完結、localhostは表示の便宜だけで必要なバックエンドではない。

## 検証記録

- code-factory最終標準ゲート: 依存整合、compile、Ruff lint/format、重要mypy、全pytest/branch-inclusive coverage、Reflex production export、9ルート静的UI、exit0。**508件/70.90%**通過（合格基準67%）。初回のWindows sandbox制限を通常実行面で解消し、設定/合格基準は変更しない。WSL推奨表示は環境情報で失敗ではない。
- 共有サービス固定入力: 市場29/銘柄17フィールドの全数値・条件・欠損を比較。新旧別々に近似計算する方式ではなく同じ共有contextを使用。
- ブラウザ実操作（Codex Browser）: 6画面×320/736/1024/1440×light/dark=48条件、ページ全体横overflowなし、エラーなし。すべての名称付き詳細、リンク、6社会計/複数方式、テーマ36組合せ/検索解除、株価10期間/スケール組合せ/6凡例/日付キー、legacy市場履歴値を確認。
- 原資料と区別したsynthetic fixture: −10%/0/+10%/null、対数非正値と欠測分断、出来高0・価格全系列off、候補→保存銘柄/未保存CLI。架空数値は実資料照合に使用しない。
- 正常v2+legacy v1の複数ファイル読込と不正混在のatomic拒否を確認。後者で有効ファイルだけ先に追加せず、以前の画面を維持。
- 最終追加: 幅変更の対象が別タブだった検査を破棄し、選択中タブでrequestedWidthと実innerWidthを照合して48条件を再実行。320/736/1024/1440各12条件、overflow/エラー0。株価チャートはResizeObserverで幅追従、320幅ではviewBox280×350/日付3目盛、期間/系列選択を保持して読める軸にする。
- 保存ファイルの実読込関数を可視テストページで29条件検査。正常6社/legacy v1を受理、不正なfact/単位/出典/会社/期間、セグメント欠落・重複・調整漏れ、TTM重複/偽合算/原値不一致、評価額文字列・重複方式を拒否。再現: `.venv\Scripts\python.exe .states/test_browser_import_contract.py` → `.states/migration_browser_final/import-contract.html`。
- 最終runを表示したまま、この作業が起動した127.0.0.1:8767だけ停止。Test-NetConnection=Falseを確認して6画面/財務評価/期間・線形・日付キー操作が動作、外部assets0、CSP connect-src none、エラー0。通信設定を変更していない。終了後に表示サーバーを復帰。
- 詳細の実操作記録は `.states/migration_browser_final/acceptance.json`。最終スクリーンショット `overview-1440-light.jpg` / `stock-320-dark.jpg` を保存して画像確認。承認済み総覧の配置・色・密度を維持し、日付/出典/未確認は実データ通り。株価のポインター操作、欠測/null・非正対数の2分断、0出来高、全価格offの出来高4本、候補→保存銘柄/未保存CLIも最終assetsで再確認。

取得状態の限界: Finnhub403、EDINETキー未設定、native TOPIX404による明示ETF代理、一部provider timeout、optional TA-Lib不足を隠さない。JP原資料の公式IR確認にはEDINETキー不要。未取得をデータ0・予測合格・適格候補へ置換しない。

今回の完了範囲はローカル版。旧Reflex/HFは維持。追加課金、売買、外部公開、ChatGPT/Vercel接続、commit/push/deploy、停止は実施しない。

## 終了条件の確認

|条件|結果・証跡|
|---|---|
|1 共有サービスとの数値/条件/欠損同等性|29市場/17銘柄の固定比較、意図した変更を対応表に明記|
|2 全機能/操作の受入|対応表全行の固定/ブラウザケースと操作表示。raw JSON保管だけを合格にしない|
|3 6社照合|全社audit complete、未調査0。JPM旧訂正差分取得不能/非開示等は経路・影響付き正常状態|
|4 4方式・不正停止|Apple2方式/JPM/PLDの実資料3ケース、期間/単位/二重/調整等の拒否テスト|
|5 ブラウザ|最終48条件・6社・全フィルター・チャート・リンク・import・キーボード・明暗・負値/0/null・通信なし|
|6 標準ゲートと往復|508件/70.90%、build/static通過。実取得→資料追加→通信禁止resume→保存→再読込、元値不変|
|7 成果物・手順|機能対応表/本6社記録/JSON証跡/HTML・Markdownプレビュー/操作・来歴/2Skill/progress更新|

上記のローカル実装・検証の未解決項目は0。取得不能を取得成功とする意味や、将来の新資料・全provider・全会社の自動会計確認を保証する意味ではない。
## 2026-10-08追加受入：共有入口・一括更新

`Open-Investment-Research.cmd` → ローカル更新入口。別のプロジェクト内Codexチャットは `research.py update --open`。日米またはJP/US市場・指数・テーマ/構成銘柄/既存範囲候補・市場方針・取得状態を1操作に集約し、個別株・会計・企業価値・解釈は元の日付/出典を保持。全体更新で企業原文を自動確認したとは表示しない。

- `tests/test_research_workbench.py`：全体/市場別の範囲、個別深掘り/課金なし、元入力不変、失敗/前回値分離、provider部分/古い状態、保存再読込/失敗時表示保持、後から追加した個別分析の集約、OSロック/二重実行、Host/Origin/token/形式/サイズ/任意ファイル拒否、CLI大まかな更新/市場alias。
- 標準code-factory gate：523passed、coverage71.38%、依存/compile/Ruff/mypy/Reflex export/9-route静的UI通過（`.states/research-workbench-gate-closeout.log`）。追加CLIケースを含む15focused workspace tests通過。初回Git/Bun/CIM制限は実行面の問題で、承認済み通常環境で同じ標準ゲートを通過。
- 実ブラウザ：6画面×320/736/1024/1440×明暗48条件。320幅ファイル選択の横はみ出しを修正後0件。日米方針、6銘柄の出典付き解釈1件ずつ、更新中の旧画面操作、対象選択、完了後表示を確認。iframe切替時のMutationObserver警告を記録。親/子アプリのどちらのスクリプトにも同APIがなく、検査ツール由来と推定（画面操作は継続）。ブラウザログが完全に0件という受入ではない。
- 実取得：全体UI `ad612d30-47cc-4fa4-99bd-b19d9079d852` → 全体CLI `daaf00c1-bbdc-430e-8ff5-16ac0b362f6e` → JP-only UI `e46cc1e6-c33e-4664-a9a5-a662547a1998`。最終にはprovider不足/古い状態をpartialと明示、US保存値は維持。US76/JP34テーマ、保存済み6社と6解釈。原本不変、current.jsonはatomic参照。
- 利用入口は `http://127.0.0.1:8768/`、保存画面は最終runのdashboard.html。スクリーンショット `.states/research_workbench/browser/final.jpg`。外部公開・常駐登録・新依存・売買・追加課金・本番停止・commit/push/deployなし。

## 2026-10-08追加受入：市場の接続表示・テーマ行内展開

今回の変更対象はローカル保存画面。総覧の承認済み配置、分析計算、取得機能、株式の条件判定、原資料・観測日は変更しない。

|対象|変更と受入|
|---|---|
|方針のタブ伸長|小画面のgrid先頭行45px／ボタン44pxを固定。短い日本方針を含め、736×1440でも余白がタブに配分されない|
|市場29項目|構造／テーマ・資金動向／信用・ボラ・心理／予測・検証／価格・水準／日本条件／任意取得に全項目を一度ずつ配置。主要観測は表示し、根拠詳細は同じ項目の近くで展開。市場→該当テーマ・方針を接続|
|専用表示|期間別モメンタム、ETF代理、時間軸、ドライバー、リスク標識、支持抵抗、日本条件を観測行で表示。市場資産・チャート・予測・オプションの専用表示と全保存値を保持|
|テーマと代表銘柄|テーマ名から直下に代表銘柄を展開、複数同時表示、Enter/Space、数値並替え後も同じテーマに紐づく。登録順・欠損銘柄を保持。保存済み分析へ移動／未保存はCodex調査CLI案内|
|期間・欠損|取得率ヘッダーと値は選択した1週／1か月／6か月へ連動。代表銘柄の保存済み20営業日とテーマ1か月21営業日を区別。旧形式の期間不明、負値、0、未確認を別表示|

- 変更ファイル：`src/research/assets/dashboard.css` / `dashboard.js` / `specialized.js` / 新規`market.js`、`src/research/render.py`、`tests/test_research_dashboard_contract.py`、操作・機能対応・本受入文書、repository `research-dashboard` Skill、`progress.md`。
- 標準コマンド `.venv\Scripts\python.exe scripts/check.py --coverage`：最終**525passed／71.27%**、依存・compile・Ruff lint/format・重要mypy・Reflex production export・9ルート静的UIが全通過。対象pytest100件も通過。初回sandboxのGit MSYS/Bun/CIM制限は実行面の失敗として区別し、同じ標準ゲートを承認済み通常実行で通した。設定・基準は変更しない。Skill検証も通過。
- ブラウザ：全6画面×4幅（320/736/1024/1440）×明暗×2高さ（1000/1440）の96条件。さらに変更3画面×日米×4幅×明暗×2高さの最終96条件を、対象タブの実幅付きで確認。ページ横overflow0、mobileボタン44px。後半に別タブへ幅変更が適用された旧96条件は合格記録から除外し、新しい実幅照合付き検査に置換。320暗表示の展開済み代表銘柄も横overflow0。
- テーマ72組合せ（2市場×3期間×3方向×4順位）、検索、複数展開、数値列並替えの行・銘柄対応、キーボード、市場→テーマ→保存銘柄／未保存案内、全29項目の詳細、保存6社のチャート・会計・複数評価を実操作確認。
- 別の合成fixtureで負値／0／欠損、代表順序、期間別取得率、旧形式の期間不明を確認。v1/v2複数読込が成功し、不正混在はatomic拒否で以前の表示を保持。合成値は実資料ではない。ファイル選択操作の検査ツール側待ちが非常に長かったため、成功後は繰り返さない。
- 自己完結HTML／CSPを保持。この作業が起動した8768表示サーバーだけ停止して接続不能を確認後、読込済み6画面と展開操作が継続動作。サーバー復帰済み。直接file://を開く検査はブラウザのURL制限で未実施であり、制限を迂回しない。通信なし動作は読込済み画面と出力構造で確認した。
- iframe切替時のMutationObserver警告2件は、当該APIを親子のアプリスクリプトが使用していないことから検査ツール由来と推定。操作は継続可能。アプリ由来の例外は観測されなかったが、console完全0とは報告しない。他ブラウザ／実機の検査は今回の対象外。
- 証跡フォルダ：`C:/Users/shusk/.codex/visualizations/2026/09/21/01a0c4b0-7c2a-72f3-b164-7c0d11261724/`。`browser-acceptance.json`、`market-connected.jpg`、`theme-inline.jpg`、`policy-fixed-736.jpg`、`theme-inline-320-dark.jpg`を保存・画像確認。新assetsの自己完結`investment-dashboard.html`も保存。
- 原run `d8438fb4-b5be-4322-b694-8a2a165575cc` のJSON SHA256 `764b0e8c49a8c6f7d3c302f9d0a4a23325fe22eecdf36454e3a2176959823de2` とcurrent参照は変更なし。UIのための新規取得、モデルAPI、追加課金、commit/push/deploy、外部公開、本番停止なし。プレビュー入口 `http://127.0.0.1:8768/` で「保存結果を表示」を押すと最新UIで再描画する。
