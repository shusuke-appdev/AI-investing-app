# Codex投資リサーチ / ローカル実装と受入状態

2026-10-24運用方針：[Codex運用](CODEX_OPERATION.md)を優先します。通常の回答はチャットと保存Markdown/JSON。以下の画面・ローカル入口は任意の補助で、アプリ化・公開は行いません。

2026-10-23追補：[地合い・業種・テーマ調査](TOPDOWN_RESEARCH.md)が現行ローカル版の画面・6期間・業績更新・v3保存の仕様です。以下の旧版説明と重なる箇所は追補を優先します。既存の個別会計・評価・研究詳細は維持します。

更新: 2026-10-11。市場→テーマ→銘柄を辿るグラフと比較表へUIを再設計。変更内容・設計資料・実測は [UI再設計の受入記録](RESEARCH_UI_REDESIGN.md)。取得と29項目の対応は [市場再構成の受入記録](MARKET_REDESIGN_ACCEPTANCE.md)。本番Reflexの置換・停止は未実施です。

## 使い方

総覧で指数推移と市場位置、同じ算定期間の強いテーマを見ます。テーマ名を押すと代表銘柄を同じ行の直下で比較でき、保存済み銘柄は価格チャートと主要条件へ進みます。個別株は「価格・条件」「成長・事業」「企業価値」「資料・計算」を切り替えます。戻ると検索・期間・並び順・展開状態を保持します。一般的な留保・操作手順・計算全文は詳細にまとめ、欠損・前回値・観測日・未成立条件は対象の近くに表示します。

### 市場・テーマの見方

標準の市場画面は、①中期基調と参加、②短期価格位置と公式予定、③テーマと代表銘柄、④金利・信用・為替等、⑤条件付きの接続・反証・次の確認、を初期表示します。期間や対象が異なる観測を一括で強気／弱気へまとめません。出典・算定内訳と旧29項目は研究詳細で確認できます。展開操作では通信取得しません。

テーマの初期期間は6か月。登録順の代表3銘柄が順位と同じ行にあり、名前を押すと直下で全代表の同期間値を比較できます。1週5／1か月21／6か月126営業日ごとに構成銘柄中央値の市場相対騰落順で並べ、取得率60%以上・min(3,登録数)を検査します。保存済み銘柄は分析画面へ、未保存銘柄は表示された依頼文をコピーしてCodexへ依頼。代表銘柄は推奨・財務確認済み候補ではありません。旧保存の20営業日・期間不明値は新期間へ読み替えません。

### 普段は一度の操作で更新・表示

リポジトリ直下の `Open-Investment-Research.cmd` をダブルクリックすると、ローカル入口が開きます。既定は「日米まとめて」「標準（5つの問い）」。「投資更新」を押すだけで、市場・指数比較・期間別テーマ／代表銘柄・接続分析・同じ根拠の方針・取得状態を更新し、完了後に表示が切り替わります。日本だけ／米国だけも選べます。起動・保存結果を表示では取得しません。「研究詳細（旧方式）」は既存分析の明示更新です。

このチャットに限定されません。Codexで **AI-investing-appプロジェクトを選んだ別チャット**でも「投資更新」で同じ一括更新を使えます。「日本だけ更新」「米国だけ更新」「保存済みの結果を開いて」も利用できます。プロジェクトを選んでいない他チャットやChatGPTへの自動接続ではありません。

```powershell
# 日米の非個別研究を一括更新して保存結果を開く
.venv\Scripts\python.exe scripts\research.py update --profile standard --open
.venv\Scripts\python.exe scripts\research.py update --scope JP --open
# 取得せず、更新ボタン付きのローカル入口を起動
.venv\Scripts\python.exe scripts\research_workbench.py --open
```

個別株の深掘りは「トヨタを分析して」など銘柄を指定。全体更新は保存済み個別株・財務照合・企業価値・Codex解釈を元の基準日のまま保持します。標準では個別企業の原資料確認・候補の財務スクリーニング・旧予測モデル・配分・複合心理・SQ警戒を実行しません。方針は市場の同じ接続分析を参照し、別の結論を再計算しません。

### 標準／研究詳細と確認済み入力

`update / overview / market / theme / policy` の新規取得は `--profile standard` が省略値です。既存29項目を更新したいときは `--profile advanced`。オプション・FOMOはadvancedでも別の明示許可／指定が必要です。段階指定refreshは旧方式の明示更新として維持。replay／resumeは元のプロフィール・取得入力を保持し、再取得しません。標準で更新しない旧結果は「今回の対象外」で元の日付を維持します。

米金利・実質金利はFREDの公表単位%を維持し、変化は差×100のbp。日本10年は財務省の当月・過去CSVを合わせ、同日重複は当月公表値優先と出典を記録。未完了のUTC当日日足は使わない保守的な更新です。疑わしい価格の不連続は倍率で修復せず、関連MA・支持抵抗・相対順位を停止します。信用と株価／VIXの接続には共通観測日の窓を別に保存し、最新観測の日時は変更しません。

JPXは無許諾の二次利用・再配信を禁止しているため自動収集しません。許諾と原資料を実際に確認できた場合だけ、下の形式で入力できます。数字・確認・許諾を捏造しないでください。新旧Excelの自動解析ではなく、各公表版の金額列・対象市場・海外投資家区分・訂正を確認した正規化入力です。千円は原表で確認した場合だけ円へ×1000し、現物と先物・株数・貸借を合算しません。

```json
{
  "version": "reviewed-market-input-v1",
  "jpx_weeks": [{
    "period_start": "2026-09-28", "period_end": "2026-10-02",
    "net_amount": 0, "unit": "JPY", "scope": "cash_equity_foreigners",
    "source": "https://www.jpx.co.jp/実際の公表資料.xlsx",
    "locator": "実際のシート・市場・金額買越セルと原単位・訂正確認",
    "checked_on": "2026-10-09", "opened_and_checked": true,
    "permission_confirmed": true, "permission_basis": "実際の許諾根拠"
  }]
}
```

上は形式例で、実データ・許諾を表すものではありません。`update --scope JP --market-inputs reviewed.json` で使用。入力最新週と非重複・連続4週を別表示し、不足週を0にせず、重複を拒否します。訂正前後を同じ週として二重登録せず、最新確認版の1行を残しlocatorに版と訂正を記録。通常更新は保存済み入力を再利用し、確認日を進めません。14日より古い週はstaleです。BLS取得不能や会合の時刻未定も理由付きで表示し、予定や予想値を推測しません。

更新には既存providerのキャッシュ・鮮度・待機時間制限が適用され、最新時刻の全項目取得を保証しません。欠損・古い観測日・取得失敗を明示します。失敗した段階は前回値と今回の試行を分離し、保存失敗時は以前の画面を維持。CLI/画面の二重更新はOSロックで止めます。ブラウザを閉じても更新は続きますが、PC終了時は中断するので再起動後に再実行してください。起動後は `http://127.0.0.1:8768/` をブックマークできます。別サービスがこのポートを使う場合は奪わず、`--port`で別ポートを指定します。

入口は自分のPCの127.0.0.1だけに待受。秘密情報や任意のリポジトリファイルを配信せず、更新POSTにはHost/Origin/実行時token/形式・サイズを検証。新規依存・常駐登録・外部公開・課金・売買はありません。画面のボタンはオプションと過熱スキャンを実行しません。

### 個別機能・資料追加

リポジトリで次を実行します。Codexには「investment-researchスキルで、米国／日本の調査を実行して」と依頼できます。

```powershell
.venv\Scripts\python.exe scripts\research.py overview
.venv\Scripts\python.exe scripts\research.py market --market JP
.venv\Scripts\python.exe scripts\research.py theme --market US
.venv\Scripts\python.exe scripts\research.py stock --ticker AAPL
.venv\Scripts\python.exe scripts\research.py stock --market JP --ticker 7203.T
.venv\Scripts\python.exe scripts\research.py policy --market US
.venv\Scripts\python.exe scripts\research.py diagnostics
```

保存先はgit対象外の `.states/research_runs/<unique-directory>/`。同じ入力を `research.json`、自己完結の `dashboard.html`、`summary.md` に保存します。保存画面はファイルを開くだけで使え、外部通信、CDN、バックエンド、モデルAPIを必要としません。画面の「データ状況」で複数の保存結果を読み込めます。ローカル入口の更新ボタンは別のPython処理を呼び、保存画面自体は取得しません。一括更新の最新保存先は `.states/research_workbench/current.json` にatomic記録。保存済み個別株の追加結果も次回起動/更新時に集約します。元のファイルは書き換えません。

```powershell
.venv\Scripts\python.exe scripts\research.py overview --replay <research.json>
.venv\Scripts\python.exe scripts\research.py stock --resume <research.json> --evidence <evidence.json>
.venv\Scripts\python.exe scripts\research.py overview --replay <overview research.json> --attach <stock research.json> --attach <policy research.json>
```

replayは元の実行ID・入力・日時を保持。resumeは価格・市場・候補を再取得せず、追加資料から財務・評価・方針を再計算し、新しいIDと元の実行への参照を保存します。外部候補の追加スクリーニングは新規theme実行で行います。新規スナップショットはv2、v1も変更せず読めます。報告作成時刻、観測日、資料公開日、取得・確認時刻は別の意味です。実行completedは処理完了だけで、データ完全性や投資判断の完成を意味しません。

## データ取得と目的別画面

|機能|取得・計算の所有者|画面・Codexへの接続|検証と境界|
|---|---|---|---|
|日米指数比較|comparison → 既存Yahoo履歴／Stooq TOPIX|総覧の2チャート、期間・実値・騰落率・出典|4系列live取得。正確な共通観測日で初日100。休日・欠測補完なし|
|TOPIX代替|直接系列を先に試し、失敗時だけ1306.T|TOPIX連動ETF・代理／調整済み終値と表示|直接指数とETFを混ぜず、ETF価格を指数値としない|
|市場基本2＋27分析|既存market_dashboard各段階 → MarketDashboardContext|資産別一覧・履歴3グラフ・専用予測/OOS/options、名称付き詳細、総覧/policy|固定入力29フィールド比較、専門表示/操作確認。各status・警告を保持|
|テーマ順位|standard：構成銘柄中央値の市場相対騰落、advanced：既存comprehensive|標準Top5と同じ5件の6か月棒、期間表、同じ行の代表銘柄／検索・方向・順位|標準は6か月相対順へ意図して変更。旧総合点・1か月棒は旧方式の研究詳細。取得率・実観測日を保持|
|リーダー探索|登録銘柄＋review済み外部資料 → 既存leader screen|テーマの候補、財務確認待ち、外部未検証、除外理由|既存5テーマ・20登録＋20外部・最大40銘柄・15財務・10候補の境界。モデル探索/cache不使用。非空固定入力で確認|
|個別株基本2＋15分析|既存stock context・trade service|主条件、終値/MA10/20/50/200/出来高の専用チャート、価格帯別表示、17詳細、ニュース|Stage2／RS／VCP／出来高／成長／Entryを個別表示。新しい総合点なし|
|企業価値|純Python equity_valuation／source-linked valuation|provider参考値と資料ベース値を分離|DCF、全セグメントSOTP、金融残余利益、REIT FFO/AFFO。固定入力で通貨・単位・3ケース確認|
|一次資料・財務時系列|Codexが原文を開く → evidence／FinancialHistory|資料リンク・確認記録、会社見通し・事業別・リスク、3年＋最新中間の不足表|自動URL検査を真実性確認としない。単位変換、期間、連結区分、会計基準、同一銘柄・source/value照合|
|方針|市場＋テーマ＋最大5候補＋資料 → deterministic policy|観測、成立条件、反証、不足、条件付き確認、無効化、次の確認を画面・Markdownに保存|研究用、注文指示なし。今回liveは適格候補0件をそのまま表示|
|過熱スキャン|明示した既存米国ユニバース → build_fomo_scan_context|市場の過熱候補詳細|market／policy --market US --scan-fomo。日本全体のスキャンと偽らない。opt-inを固定入力検証|
|市場オプション|既存米国provider、明示許可時のみ|市場参考だけ。個別株の主条件は書き換えない|--allow-optionsはUS market／policy限定。追加取得はcredit消費の可能性。今回live未実行|
|データ状況|既存health／manifestの記録＋各packet状態|独立画面、ローカル読込、作成時刻と元の実行を確認|diagnosticsは履歴で、接続の生存確認ではない。不正ファイルは一括読込前に拒否|

市場・銘柄の正確なフィールド対応は `src/research/catalog.py` と [全機能・操作対応表](RESEARCH_FEATURE_PARITY.md)。JSONの保管だけをUI同等性と呼ばず、専用表示・名称付き表・出典への接続を残します。判定falseや実際の0、null、対象なし、partial、stale、research_onlyを区別します。日本の信用欄に米国系列を使う場合はその対象を明示し、日本の信用値としません。

日本の市場条件は欠損を0点にした総合評価を除外し、EPS改定／海外投資家実フローを価格proxyから確認済みにはしません。FinnhubにはYahooの.T記号を送りません。既存キャッシュ・再試行・時間制限を再利用し、無制限取得や自動追加課金はしません。CLIプロセス内のINVESTMENT_RESEARCH_NO_MODELガードが、誤って呼ばれたGeminiクライアントの利用も止めます。常設設定・認証情報には変更を加えません。

## 一次資料の契約

`src/research/evidence.py` の資料v2がsources、claims、missing、financial_histories、valuations、accounting_reviews、segment_ledgers、derivations、interpretations、external_candidatesを検査します。旧資料v1も読めます。資料には公開／確認日、URL、ページ・箇所、短い確認記録、primary／independent、opened_and_checked／unverifiedを記録。将来日付、重複、他社資料への参照を拒否。reviewは入力者の確認記録で、Pythonによる内容認証ではありません。

FinancialHistoryは3つの連続年度末と最新中間、通貨、元の単位、期間境界、連結・単体、会計基準、指標definitionを保存します。一般企業／金融／REIT別に必要指標の不足を算出します。資料自体が最新か、指標定義が妥当か、企業の特殊会計を全て照合したかはCodexの確認事項です。

半年決算はfiscal_half、合算12か月はttmとして構成期間・出典・非重複・欠落・和を検査。accounting_reviewsには原表の符号付きreconciliationsと訂正確認source/影響、segment_ledgersには全報告事業・本社調整/消去・全社合計を記録します。deriveの引用URLだけでは算定せず、原factの値・単位・期間・sourceと一致を要求。未調査と確認済み非開示/適用対象外/取得不能を区別します。

評価はticker/method/基準期間（REITは指標も）で識別。DCFとSOTPを同じ銘柄に併存でき、旧単一filing_valuationは互換用に残します。金融は親会社普通株利益/簿価/株数/ROE、REITは原調整CFとOPを含む同範囲の分母を揃えます。銀行預金を一般企業負債として控除しません。金融/REITに不要な現金・負債は必須ではありません。逆DCFはDCFだけ、株価観測日と評価基準期間を併記。範囲外の逆算を上限値で成功したように表示しません。

Codex解釈は元run_idとinput_paths（例 `/sections/7203.T/analysis`）へ結び、観測/会社見通し/仮定/反証/sourceを保存します。日本の.T記号はJSON Pointerで参照。解釈文は既存数値の判定を変更しません。

## 項目別の更新とチャート操作

```powershell
.venv\Scripts\python.exe scripts\research.py market --market JP --refresh <research.json> --stage summary
.venv\Scripts\python.exe scripts\research.py market --market US --refresh <research.json> --stage theme-flow
.venv\Scripts\python.exe scripts\research.py market --market US --refresh <research.json> --stage credit-risk
.venv\Scripts\python.exe scripts\research.py market --market US --refresh <research.json> --stage vol-sentiment
```

保存済み市場の指定段階と必要な派生結果のみ更新。無関係な以前の結果・status/provenanceは保持し、失敗時は以前の値と今回の失敗attemptを区別します。同じエラーの再発も成功扱いしません。options段階は別途US `--allow-options` が必要（credit消費の可能性）。FOMOは新規US実行で明示 `--scan-fomo`。resume/replayには取得指定を混ぜられません。

株価チャート内の期間・線形/対数・各系列チェックは保存価格だけを切り替えます。グラフ上の位置/矢印/Home/Endで日付値を確認。欠測や対数の非正価格は線をつなぎません。価格を全て消して出来高だけ確認できます。指数期間とは独立。標準テーマは1週/1月/6月、方向、市場相対上下/取得率、検索を操作し、代表銘柄から保存銘柄を開けます。旧総合順位は旧方式のまま研究詳細に残します。

source-linked評価はfcff_dcf／sotp／residual_income／reit_multiple。貨幣入力は基礎通貨単位、株式数は実数。中間CFを年度CFとしない。借入利息後の営業CF−設備支出をunlevered FCFFと断定しない。期末株式数とEPS用の加重平均希薄化株式数は別指標です。SOTPは全報告セグメントと出典付きcorporate adjustmentが必要。金融ROE・割引率、REIT倍率、成長率は仮定と表示します。数量は同じ期間・単位変換・sourceと照合し、計算overflowを評価額として出しません。

SECの無料提出履歴取得はstock --ticker AAPL --filings-cik 320193。実際の連絡先入りSEC_USER_AGENTが必要で、未設定ならunavailable。連絡先の捏造・表示はしません。[SEC API公式説明](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)。提出履歴は未検証の資料候補です。日本はEDINET検索・公式会社IRを使え、IRのWeb確認にはEDINETキー不要。Company Factsだけでセグメントの完全性は判断しません。

## 画面デザインと受入

研究用一覧性を優先し、総覧に個別株は載せません。上段2チャート→3パネル→Top5期間比較→2つの参考表。6画面、白／冷灰、青・青緑、薄い境界、6px角丸、表の数値右寄せ。設計Skillは `.agents/skills/research-dashboard/SKILL.md`、テンプレート・tokensは `src/research/assets/` に保存しました。

承認画像との比較で確認した5項目以上:
- 2指数比較の横並びと右側の実値・観測日。
- 左ナビと総覧／市場／テーマ／銘柄／方針／データ状況の6入口。
- 3パネルとTop5表の順序、返り値で順位を変えない棒表示。
- 細い罫線・冷灰の見出し・青/青緑・統一余白。
- 表の密度と右寄せ、数字字体、長いテーマ名の折返し。
- 小さい幅は縦積み＋表内横スクロール。日本語1文字ずつ縦に崩れない。
- サンプルの日付・架空数値はコピーせず実観測値を使用。実資料の警告・出典を追加する分、承認モックより情報行が増えるのは意図した相違。

ブラウザの再現用コマンド:
```powershell
.venv\Scripts\python.exe scripts\research_browser_smoke.py <dashboard.html> --stock <AAPL research.json> --stock <7203.T research.json>
.venv\Scripts\python.exe scripts\check.py --coverage
```

ブラウザは320/736/1024/1440 light/dark、日米切替、5期間、検索／解除、数値ソート、6画面、複数保存ファイル読込、銘柄選択、詳細展開、console、画面横はみ出しを検査。不正ファイル混在時に有効ファイルだけ先に追加しないことも検査。今回の実操作はCodex Browserを使用しました。既存Python smokeはCLI環境用の補助で、今回のブラウザ証跡を置き換えるものではありません。明暗は画面右上の「表示」で切り替えられます。

## 実データ確認とローカル完了

最新の全機能受入、6社の原資料照合、4方式の実例、標準gate・ブラウザ結果・取得制約は [移行版受入記録](RESEARCH_MIGRATION_ACCEPTANCE.md) を参照。Windows sandboxのGit MSYS／Reflex実行制限は通常の承認済み実行面で解消し、判定基準・設定は変更していません。

`--attach` は追加スナップショットの元入力・日時を変更せず画面へ同梱し、attached_01.json等も保存します（最大20件、各20MB）。画面からの複数JSON読込も各20MB以内で一括検証してから追加します。最終6社previewは `.states/research_runs/a4355623-3c00-4201-ba95-f81a4f6051e8/dashboard.html`。本番公開ではありません。

2026-10-06の日米overviewは4系列を取得し、US共通最終日は10月5日、JPは10月6日。Stooq TOPIXは404で1306.Tに代替。一部市場段階のtimeoutは消さず保存。未対応VPNは[発行体資料](https://assets.globalxetfs.com/dev/documents/dtcr/prospectus-regulatory/Tailored-Shareholders-Report.pdf)で2024年4月1日の記号変更を確認しDTCRへ更新しました。

2026-10-07にApple/トヨタ/JPM/MUFG/PLD/NBFの直近3年と最新公表期を照合。会計auditは全社未調査0。原文で確認した非開示/適用外と旧訂正資料の取得不能は理由・出典・影響付きで残します。4方式はApple DCF/SOTP、JPM残余利益、PLD CoreFFOで3ケースを算定。トヨタ/MUFG/NBFは追加の評価仮定なしに全社値を作りません。原数値/全セグメント/調整/期間・帰属・訂正の証拠は `.states/reviewed_evidence_20261007.json`、再現/再読込は `.states/migration_roundtrip_20261007.json`。

旧Reflex/Gemini依存・既存本番CI・HFは復帰先として保持しています。ローカル移行完了は本番停止/旧依存完全撤去の承認ではありません。追加モデル/有料options取得・外部設定・commit/push/deployは行っていません。ChatGPT/Vercel接続や公開も未実施で、別途明示承認が必要です。
