# 適応型銘柄分析・価格帯別出来高 設計

## 目的と境界

本機能は既存の確率シグナル、Entry Framework、`MarketContext`、
`StockSignalContext`を置き換えない。価格帯別出来高、適応型ファンダメンタル、
根拠一致度を追加コンテキストとして提供する。欠損値をゼロへ変換せず、
算出不可・部分評価・上限適用を明示する。

## 価格帯別出来高

- 入力: 取得済み日足OHLCVの直近126営業日。最低60営業日。
- 集計: 全価格レンジを24帯へ分割し、各日の出来高を当日の安値～高値と
  重なる価格帯へ均等密度で配分する。
- 出力: POC、70% Value Area（VAL/VAH）、主要集中帯、現値直下の支持帯、
  現値直上の抵抗帯、24本の横棒表示用データ。
- 市場: USはSPY/QQQ、JPは1306.T/1321.T。いずれも指数連動ETF proxyであり、
  指数自体または取引所約定別の実測Volume Profileではない。
- トレード分析: profileの支持・抵抗・帯下限を押し目、ブレイク、無効化へ
  優先使用し、算出不能時のみ従来の直近高安・移動平均へフォールバックする。
- v1では市場戦略レジームのスコア式を変更しない。

## 三層分類

### 1. 時価総額規模

- US: 2026年FTSE Russell indicative rangesを運用境界に使用する。
  大型は175億ドル以上、中型は57億ドル以上175億ドル未満、小型は57億ドル未満。
  境界±10%を`borderline`とする。
- JP: J-Quants Scale Categoryを優先し、Core30/Large70→大型、Mid400→中型、
  Small/Small500/Micro→小型へ対応する。
- JP fallback: 1兆円以上→大型、1000億円以上1兆円未満→中型、
  1000億円未満→小型。これは公式TOPIX分類ではないproxyである。

### 2. バリュー・グロース

- バリュー: B/P 50%、予想益利回り30%、FCF利回り20%。
- グロース: 売上成長60%、利益成長40%。
- 業種基準の0.5倍以下=0点、1倍=50点、1.5倍以上=100点として線形補間する。
- 小型の成長要求1.25倍、中型1.0倍、大型0.75倍。
- 両側の差が10点以上なら優位側、差10点未満はブレンド。
- バリュー1因子・グロース1因子以上かつ全5因子の60%以上を必要とする。
- 赤字・負の成長は実在する低評価、未取得は欠損として扱う。

### 3. 業種プロファイル

主力事業を示す`industry`を広い`sector`より優先し、一般、ソフトウェア、
半導体、銀行、保険、REIT、エネルギー・素材、医薬・バイオ、公益・通信へ分類する。
未対応時は一般プロファイルをfallback表示する。

- 銀行: ROE/ROTCE、簿価成長、CET1、資産品質、P/B・P/TBV。一般D/E・流動比率・
  EV/EBITDAを除外する。
- REIT: FFO/AFFO、NOI、稼働率、配当性向、Net Debt/EBITDA、P/AFFO・NAV。
  通常PERとEPS成長を除外し、FFO系KPIなしでは算出不可とする。
- 赤字バイオ: キャッシュランウェイとパイプラインを必須とし、不足時は算出不可。
- 保険は取得できた専用KPIだけで部分評価し、一般企業用D/E・流動比率を使わない。

基準値は`src/data/fundamental_benchmarks_2026.json`に固定し、ランタイム通信を行わない。
基準日から548日超で69点上限とする。JP評価で同基準を使う場合はproxy表示する。

## 5評価軸と上限

成長、収益性、キャッシュ創出、財務健全性、割安度の5軸へ各業種KPIを割り当てる。
規模・スタイル別重みは実装定数`WEIGHTS`を正本とし、ブレンドは同規模の
バリュー・グロース重みを平均する。

- 充足率60%未満: 算出不可。
- 充足率60～79%: 部分評価、69点上限。
- 基準18か月超: 69点上限。
- 小型でキャッシュ創出または財務健全性が40点未満: 54点上限。
- SMARTはグロース株向けproxyとして残すが、新スコアへ加算しない。

## 根拠一致度

- テクニカル側 = テクニカル総合点70% + Entry Framework点30%。
- ファンダメンタル・テーマ側 = 適応型ファンダメンタル70% +
  Trend Ranking点（rank points×10）30%。
- 最終点 = 両側の調和平均。テクニカル、Entry、ファンダメンタル、
  テーマ順位のいずれかが欠損する場合は0点ではなく算出不可。
- 75以上「高」、55～74「中」、54以下「低」。
- 54点上限: Entry禁止、Stage 3/4、強い弱気テクニカル、FOMO high/extreme、
  確率シグナルAvoid。
- 74点上限: Entry未成立、確率シグナルLow/Watch、ファンダメンタル部分評価。

この点数は予測確率、購入推奨、注文指示ではなく、表示済み根拠の一致度である。
Stockの詳細パネル、Data Quality、トレード分析、AI入力では
`purchase_evidence_health` を共有し、必須4入力の欠損と上限理由を同じ内容で表示する。

## 基準の出典

- [FTSE Russell reconstitution](https://www.lseg.com/en/ftse-russell/russell-reconstitution)
- [Russell US Indexes methodology](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/russell-us-indexes-construction-and-methodology.pdf)
- [JPX size methodology](https://www.jpx.co.jp/english/markets/indices/line-up/files/e_cal2_12_size.pdf)
- [MSCI GICS](https://www.msci.com/indexes/index-resources/gics)
- [NYU Stern ROE](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/roe.html)
- [NYU Stern margins](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/margin.html)
- [NYU Stern PE/growth](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/pedata.html)
- [NYU Stern debt](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/dbtfund.html)
