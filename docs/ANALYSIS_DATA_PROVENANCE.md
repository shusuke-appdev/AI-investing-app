# 分析データ来歴台帳

更新日: 2026-08-10

## 目的

本台帳は、画面またはAI分析で利用する値が、直接取得値、ローカル算出値、proxy、推定値、モデル出力、固定フォールバック、stale cache、利用不可のどれかを明確にし、直接値への置換と誤認防止の改修バックログを管理する正本です。

## 種別

| 種別 | 意味 |
|---|---|
| `direct` | 外部データソースから取得した値 |
| `computed` | 直接値から決定的な計算で算出した値 |
| `proxy` | 本来の対象を別の観測可能データで代替評価した値 |
| `estimated` | 欠損値を数式・仮定で推定した値 |
| `model_output` | 統計・ルール・AIモデルの出力 |
| `fixed_fallback` | 欠損時に固定値を入れた値。原則廃止対象 |
| `stale_cache` | 外部取得失敗時に利用する過去の成功データ |
| `unavailable` | 必要データ不足により算出・表示できない状態 |

## 台帳

| 画面・機能 | 表示項目 | 種別 | 使用データ | 代替・発動条件 | 現在の表示方法 | 誤認リスク | 直接値への置換案 | 優先度 | 改修状態 |
|---|---|---|---|---|---|---|---|---|---|
| Market Watch / AI Recap | IBD式市場状態 | proxy | SPY、Nasdaq 100 OHLCV、Distribution Day、FTD、MA | 公式IBDデータを利用しない | データ品質ページでproxy表示 | 公式IBD Market Pulseと誤認 | 公式データを利用可能な場合だけ別指標として追加 | 中 | 専用ページへ移動 |
| Market Watch / AI Recap | CTAポジショニング | proxy | SPY価格と20/50日MA | 実ポジションデータなし | データ品質ページでproxy表示 | CTA実ポジションと誤認 | CFTC直接系列とは別物として維持 | 高 | 専用ページへ移動 |
| Market Watch / Short Forecast | CFTC TFFポジショニング | direct / stale_cache / unavailable | CFTC Public Reporting `13874A` E-mini S&P 500、Asset Manager / Leveraged Money long・short、Open Interest | 週次報告をreport date+5暦日後の次営業日から20営業日モデルだけに利用。取得失敗時は7日以内のcacheを表示するがモデル入力から除外 | 予測来歴と品質警告 | 火曜時点の建玉を公表前から使う先読み、CTA実ポジションとの混同 | CFTC公式系列として公表遅延を固定し、CTA proxyとは統合しない | 高 | 2026-07-14 追加 |
| Market Watch | Amihud流動性・板の薄さ | proxy | 日次価格・出来高 | 板・約定データなし | 市場マイクロストラクチャー内 | 実際の板流動性と誤認 | bid/ask・market depthへ分離 | 高 | 台帳化済み |
| Market Watch / AI Recap | Unwindリスクスコア | model_output | CTA proxy、流動性proxy、VRP | ルール加重 | 総合スコア表示 | 精密な危機確率と誤認 | 構成要素と重みをUIで展開 | 高 | 台帳化済み |
| Market Watch / AI Recap | ETFリーダーシップ・資金流入 | proxy | 署名付きドル出来高、相対収益、MA | 公式ETFフローなし | データ品質ページでproxy表示 | 公式ファンドフローと誤認 | 発行体または信頼できるフローデータへ置換 | 高 | 専用ページへ移動 |
| Market Watch / AI Recap | セクター・テーマ資金流入 | proxy | 代表ETF、テーマ構成銘柄、騰落率、出来高、参加率 | 直接資金流入データなし | データ品質ページでproxy表示 | 実資金流入額と誤認 | 直接フロー取得時に別列で追加 | 高 | 専用ページへ移動 |
| Market Watch / Stock | ファンダメンタル対フロー歪み | model_output | ファンダメンタル・フローのヒューリスティックスコア | ローカルスコア差 | 歪み候補カード | 統計的裁定機会と誤認 | 学習外検証、構成値、信頼区間を追加 | 高 | 表示対応済み |
| Market Watch / AI Recap | 日本株相対優位 | proxy | 日経平均とS&P500の相対騰落率 | 直接資金配分データなし | 日経6条件内で代理表示 | 海外資金流入と誤認 | 投資部門別売買状況を直接取得 | 高 | 既存表示あり |
| Market Watch / AI Recap | ショートカバー発生 | proxy | 日経急反発と出来高増 | ショート残高直接データなし | 日経6条件内で代理表示 | 実際の買い戻しと誤認 | 日証金・貸借データを直接取得 | 高 | 既存表示あり |
| Market Watch / AI Recap | 日経理論値上方修正 | proxy | 日経20日・60日価格トレンド | EPS/PER改定データなし | 日経6条件内で代理表示 | 業績上方修正と誤認 | 指数EPS、予想PER、業績改定幅を取得 | 高 | 既存表示あり |
| Market Watch / AI Recap | 海外投資家買い | proxy | 原油安、日本テーマflow | 手入力の海外投資家買越額なし | 日経6条件内で代理表示 | 海外投資家の直接買越と誤認 | 投資部門別売買状況を自動取得 | 高 | 既存表示あり |
| Market Watch / Stock | GEX | estimated / computed | オプションOI、Gamma、株価 | yfinanceは一部Gamma欠損時に推定、全欠損時は非表示。MarketData.appは主要ETF/テーマETF proxyで直接Gammaを使用 | Optionカードとデータ品質ページでquality warning表示。通常のMarket上部エラーには混ぜない | 直接GammaでもCall正・Put負はディーラー方向の簡易仮定 | 直接ディーラー建玉データを取得できる場合は別指標として追加 | 高 | MarketData.app preferredへ昇格 |
| Market Watch / Stock | オプションIV・Greeks・OI・Volume | direct / stale_cache | MarketData.appの解決済み満期チェーン、またはyfinance/cache | `preferred`ではMarketData.appを優先、204/API失敗/必須列不足/トークン未設定/満期解決失敗時にyfinance/cacheへフォールバック。`shadow`は比較検証用。current / 1W / 1M は満期別cache keyで保持 | 取得元・解決済み満期・基準時刻・mode・品質警告を表示 | Free/Trial遅延値や0DTE期限切れを現在値と誤認 | updated時刻、解決済み満期、契約プランを表示し、source/as_ofをAI入力にも渡す | 高 | 2026-06-26 期間別満期解決を追加 |
| Market Watch / AI Recap | 25Δ IVスキュー（Put IV − Call IV） | computed / direct / proxy / unavailable | MarketData.appのdelta、IV、bid/ask/mid、OI、Volume、権利行使価格 | 0.25を挟む流動性合格脚を線形補間。なければdelta差0.05以内の最寄り。IV 0–200%、bid>0、ask≥bid、spread/mid≤50%、OI≥50またはvolume≥10。失敗時の10% OTM、yfinance、旧数値cacheは表示専用proxy | 期限・銘柄ごとにmethod/status、両脚IV・delta・strike、流動性、警告、as-ofを表示・AIへ渡す。市場参照はfreshなSPY直接値だけ | Cboe SKEW指数との混同、指数横断平均、proxyを直接値と誤認 | `skew_by_ticker`を保持し、2銘柄以上の直接値だけdispersionを表示。proxy/stale/legacyはスコアから除外 | 最優先 | 2026-08-10 25Δ正本化 |
| Market Watch / AI Recap | オプション期間構造 | computed / direct / stale_cache | current / 1W / 1M のIV、PCR、25Δ IVスキュー、Max Pain、GEX、想定変動幅 | MarketData.app preferredまたはyfinance/cacheの満期別チェーン取得時 | Optionカードの期間別行、Market timeframe、AI Recap promptへ渡す | 1週間・1か月の市場予測を確定値と誤認 | 「織り込み」「想定変動幅」として表示し、source/as_of/cache_status/methodを併記 | 高 | 2026-08-10 スキュー品質契約更新 |
| Market Watch / AI Recap | VIX×SQ週アラート | computed / direct / unavailable | CBOE VIX履歴、MACD、パラボリックSAR、米国月次オプションSQ週 | CBOE履歴が取得でき、60営業日以上ある場合だけ判定。VIX履歴なしは未取得 | Market Watchの信用/フロー欄とAI Recap promptへ渡す | SQ週の暴落・底打ちを確定イベントと誤認 | `status`、SQ期日、VIX、MACD/PSAR状態、データ不足を併記し、ヘッジ警戒/底打ち候補の研究シグナルに限定 | 高 | 2026-07-05 追加 |
| Market Watch / AI Recap | Cboeボラティリティ群 | direct / stale_cache / unavailable | Cboe公式CSVのVIX、VIX1D、VIX9D、VIX3M、VVIX、SKEW、VXN、RVX、DSPX、VIXEQ | 指数ごとに取得・cache状態を保持。欠損指数を0で補完しない | Cboe SKEW指数は指数値、履歴percentile、5日変化、as-ofを明示し、短期予測・複合判定へ渡す | Cboe SKEW指数をETFの25Δ IVスキューと混同、VIX単独を下落確率と誤認 | 指標名と役割を分離し、Cboe SKEWの予測特徴量・downgrade-only契約は維持 | 高 | 2026-08-10 表示定義分離 |
| Market Watch / AI Recap | SPY/QQQ 1・5・20営業日短期予測 | model_output / unavailable | 価格・出来高、breadth/relative strength、Cboe指数群、20日だけCFTC TFF。train-only median/IQR/winsor、ridge logistic、trend、類似局面 | 最低5年学習、500件以上OOS、Brier skill>0、log lossがbaseline以下、ECE<=0.08、80%区間coverage 70-90%、類似30件以上を地平別に判定 | 上昇確率、p10/p50/p90、implied move、downside probability、OOS指標、validated/research_onlyを表示 | 研究中モデルを確定予測・全地平一括合格と誤認 | `validated`の対応地平だけ定性戦略へ利用し、research_only/staleは表示限定 | 最優先 | 2026-07-14 追加 |
| Market Watch / Stock / AI Recap | 複合センチメント判定 | model_output / unavailable | VIX/SKEW/VVIX、VIX期間構造、OCC日次Put/Call、MarketData.app完全Gamma、RSP/SPY・IWM/SPY breadth | 必要条件がすべてcurrentで揃うルールだけconfirmed。OCCは60観測未満、Gammaはproxy/incomplete、stale入力はpartial | 状態名、根拠、欠損、risk floor、警戒補正のみを表示 | 単一スコアや上昇確率補正、反発買いサインと誤認 | 確率を変更せずrisk維持/引上げとstock stance downgradeだけ許可 | 最優先 | 2026-07-14 追加 |
| Market Watch / Composite Sentiment | OCC銘柄別Put/Call履歴 | direct / unavailable | OCC consolidated daily option volume query、SPY/QQQ call/put数量 | 明示backfillで蓄積し60営業日未満はpercentile判定不可。ゼロや固定PCRを補完しない | 観測数、as_of、欠損理由を複合判定へ渡す | 未収集履歴を中立PCRと誤認 | 無料公式履歴を再開可能なローカルcacheへ保存 | 高 | 2026-07-14 追加 |
| Market Watch | IV想定価格帯 | estimated | 現在価格、IV、満期日数 | current / 1W / 1M の各オプションデータ取得時 | オプション分析内 | 予測レンジと誤認 | 想定変動幅として明示し実績比較を追加 | 中 | 期間別表示対応 |
| Market Watch | Max Pain | computed | オプションOIと権利行使価格 | オプションチェーン取得時 | オプション分析内 | 価格目標と誤認 | 算出定義と制約を個別表示 | 中 | 台帳化済み |
| Market Watch / AI Recap | PCR欠損時 `0.8` | fixed_fallback | なし | オプション欠損時 | 旧実装では中立値として内部利用 | データ取得成功と誤認 | 欠損時は利用不可にする | 最優先 | 2026-06-11 廃止 |
| Market Watch / AI Recap | 米10年債利回り欠損時 `4.0%` | fixed_fallback | なし | TNX欠損時 | 旧実装では現在値として内部利用 | 現在利回りと誤認 | 欠損時はイールドスプレッド利用不可 | 最優先 | 2026-06-11 廃止 |
| Market Watch / AI Recap | SPY PER `22` / NDX PER `30` | fixed_fallback | なし | バリュエーション欠損時 | 旧実装では現在値として内部利用 | 現在PERと誤認 | 欠損指数だけスプレッド算出対象外 | 最優先 | 2026-06-11 廃止 |
| Stock / AI Recap | SMART基準 | proxy | 直近の売上成長、利益率、EPS成長、ROE/ROA、市場状態 | 複数年・四半期データ不足 | データ品質ページでproxy表示 | 正式SMART条件達成と誤認 | 財務履歴を取得し各条件を期間単位で判定 | 高 | 専用ページへ移動 |
| Stock / AI Recap | ROAによるROE代替 | proxy | ROA | ROE欠損時 | SMART R条件に利用 | ROE直接値と誤認 | ROE欠損は未判定とし代替評価を別表示 | 高 | 台帳化済み |
| Stock / AI Recap | 確率シグナル・推奨配分 | model_output | 類似局面、forward return、walk-forward、リスクルール | 十分な履歴がある場合 | 来歴パネルでモデル出力表示 | 将来確率・推奨配分の確定値と誤認 | 校正、信頼区間、OOS履歴を強化 | 高 | 表示対応済み |
| Stock | セクター・テーマ評価 | proxy | テーマ構成銘柄、企業指標、相対収益、MA | 直接フローなし | データ品質ページでproxy表示 | 実資金流入・公式分類と誤認 | 直接フローと分類ソースを追加 | 高 | 専用ページへ移動 |
| Stock | トレード分析 | model_output / computed | StockSignalContext、technical_data、trade_setup、sector_theme_context、fomo_regime、trend_follow_diagnostics、probabilistic_signal | Stock画面で銘柄分析後にユーザーが「トレード分析」を押した場合だけ生成。追加取得なし | Stock内の展開パネル。初期表示には出さない | 売買命令・保証されたタイミングと誤認 | 売買助言ではなく、条件・無効化・リスク水準の整理として表示し続ける | 高 | 2026-06-18 追加 |
| Stock | Minerviniステージ分析 | computed | 日足終値、50/150/200日線、200日線20営業日傾き、52週高値/安値、VCP検出 | 200営業日未満は判定不能 | Stockテクニカル分析内に常時表示 | Minervini公式データや裁量判断と誤認 | 条件ごとの達成/未達、データ不足、VCPの水準を併記 | 中 | 2026-06-18 表示拡張 |
| Stock / AI Recap | 戦略別テクニカル | computed / unavailable | 日足OHLCV、25日ボリンジャーバンド、パラボリックSAR、MACD、フィボナッチ拡張、一目雲、ダウ理論、ダイバージェンス | 80営業日未満は算出不可 | Stockテクニカル分析とAI Stock Recap promptへ渡す | 売買シグナルや将来下落率の断定と誤認 | バンドウォーク終了、天井圏、ダウ理論などの条件別statusとtarget/riskを表示し、研究用の警戒材料に限定 | 高 | 2026-07-05 追加 |
| Stock / AI Recap | 日本株需給期日 | direct / computed / unavailable | 日足OHLCV、手入力または環境変数の制度信用買い残・売り残、貸株注意喚起/逆日歩フラグ | 日本株のみ対象。制度信用データがない場合はデータ不足。一般信用は含めない前提 | Stockテクニカル分析、DataResult、AI Stock Recap promptへ渡す | 信用倍率が一般信用込みまたは推定値と誤認 | `JP_MARGIN_ROWS_<ticker>` と `JP_LOAN_ALERT_<ticker>` の入力元、未取得警告、急落時買い残増加の無効化条件を表示 | 高 | 2026-07-05 追加 |
| Stock / Market | 総合テクニカル・市場環境スコア | model_output | 複数テクニカル指標と固定重み | 指標算出時 | 総合評価として表示 | 客観的確率と誤認 | 構成指標、重み、欠損寄与を表示 | 中 | 台帳化済み |
| Stock | Trend-Follow約定価格 | proxy | 翌日Open、欠損時Close | Open欠損時 | warningへ記録 | 実約定可能価格と誤認 | 欠損ケースを検証対象外にする選択肢を追加 | 中 | 既存警告あり |
| Stock | forward return / walk-forward | computed / model_output | 過去価格、固定取引コスト | バックテスト時 | 診断パネル | 実運用成績と誤認 | スリッページ感応度と期間外検証を追加 | 高 | 台帳化済み |
| Market / Stock | GARCH失敗時のACF代替 | proxy | ACF、vol-of-vol | GARCHフィット失敗時 | 内部判定に利用 | GARCH成功と誤認 | fallback使用フラグをcontextへ追加 | 中 | 未対応 |
| News / AI Recap | 決算時期の概算 | estimated | 四半期ごとの一般的時期 | 正確な決算日取得不可時 | ニュース文脈に利用 | 正式日程と誤認 | 公式IR・取引所カレンダーへ置換 | 中 | 未対応 |
| Market / Options | stale cache | stale_cache | 最後の取得成功データ | 外部取得失敗・低速時 | 来歴パネルで古いキャッシュ表示 | 現在値と誤認 | 基準日時と経過時間を常時表示 | 高 | 表示対応済み |
| トレンド/テーマ | 指定期間騰落率 | computed / unavailable | yfinance構成銘柄終値 | 指定期間を満たさない銘柄は除外。2銘柄未満または取得率40%未満のテーマは非表示。provider失敗時は空ランキングと区別して`FetchResult`のstatus・error_code・warningを保持。12時間の永続キャッシュ契約を持ち、live失敗時のみ期限内staleを明示利用 | 対象市場、期間、更新時刻、実測銘柄数・総数・取得率、cache/stale、取得警告を表示 | 短い上場履歴を長期成績と誤認、旧市場の遅延応答を現在市場の結果と誤認 | 銘柄単位の取得失敗理由は今後保持 | 高 | 2026-08-02 永続cache・latest-wins更新 |
| Stock / Market | 日本株現在値・価格履歴 | direct | yfinance | J-Quants Free価格系列は遅延するため汎用価格経路から除外 | 通常の価格・履歴表示 | 遅延価格を現在値と誤認 | 公式リアルタイム契約がある場合だけ別経路で追加 | 最優先 | 2026-06-14 修正 |
| Market Intelligence | 取得失敗した指数・セクター価格 | unavailable | なし | Finnhub・yfinance等の取得失敗 | `0.0` を表示せず項目を省略 | 市場価格ゼロ・中立と誤認 | 失敗理由を結果型へ保持 | 最優先 | 2026-06-14 修正 |
| Market / Stock / Portfolio | AI生成レポート・助言 | model_output | 画面で使用した構造化context | 明示操作時 | AI Recap / AI助言 | 事実・売買指示と誤認 | 使用来歴と制約をプロンプト・UIに常時表示 | 高 | 一部対応 |
| Portfolio | 価格未取得銘柄の時価 `0` | unavailable | なし | 現在価格欠損時 | 旧実装ではゼロ時価として集計 | 構成比を過大・過小評価 | 集計対象から除外し警告表示 | 最優先 | 2026-06-11 修正 |
| Portfolio / AI | 混在通貨の円換算総額・構成比 | computed / direct / unavailable | 各銘柄の現地通貨・現在価格、共有MarketContextのUSD/JPY、または1回だけ取得する`JPY=X` | 全保有をJPYへ換算できる場合だけ総額・weight・sector/theme・集中度を算出 | 円換算総額、現地通貨時価、通貨別小計、為替sourceを表示 | USDとJPYを同額単位で合算、為替欠損を固定レートで補完 | 為替欠損時は通貨別小計のみ、総額・weightはunavailable | 最優先 | 2026-07-14 修正 |
| Market Watch / Microstructure | Theme/Flow更新時のoption入力 | direct / unavailable | 既存OptionContextのSPY行のみ | Theme/Flowではoption chainを暗黙取得しない。明示Options更新後だけ取得済みchainを再利用 | VRP等のoption要素だけ欠損可能 | 画面更新だけでMarketDataクレジットを重複消費 | provided-only方針とcall-count regressionを維持 | 最優先 | 2026-07-14 修正 |
| 各種provider / presentation | 欠損値の `0.0`・中立化 | unavailable | なし | provider失敗・値欠損 | 一部低レベル経路に残存 | 中立市場・ゼロ値と誤認 | `DataResult` と `ProvenanceItem` を全取得層へ拡張 | 最優先 | 継続対応 |
| Market / Stock | 価格帯別出来高 | proxy | 直近126営業日の日足OHLCV | 最低60営業日、24価格帯 | POC・70% Value Area・支持/抵抗帯・横棒profile | 取引所約定別の実測Volume Profileと誤認 | 日足安値～高値への均等配分proxy、指数はETF proxyと常時表示 | 高 | 2026-06-23 追加 |
| Stock / AI Recap | 適応型ファンダメンタル評価 | computed / proxy / unavailable | provider企業指標、J-Quants Scale Category、ローカル2026業種基準 | 時価総額・スタイル・必須業種KPI・60%以上の5軸充足が必要 | Stock要約・詳細・AI入力・既存sector/theme点 | 異業種KPIの誤適用、JP基準を直接値と誤認 | 銀行/REIT/赤字バイオの専用必須KPI、fallback・JP proxy・基準日・上限理由を表示 | 高 | 2026-06-23 追加 |
| Stock / AI Recap | 根拠一致度 | model_output / unavailable | テクニカル、Entry、適応型ファンダメンタル、テーマ順位 | 4入力必須。いずれか欠損時は算出不可。Entry/FOMO/Stage/確率/部分評価で上限 | Stock上部・詳細ヘルス、Data Quality、トレード分析、AI入力 | 将来確率や購入推奨と誤認 | 高/中/低の調査ラベル、調和平均、上限理由、入力別ヘルスを表示し、既存確率シグナルを置換しない | 高 | 2026-07-01 機能別ヘルス表示追加 |

## 運用ルール

- 新しい分析項目を追加するときは、同じ変更で本台帳へ登録する
- `fixed_fallback` は原則追加しない。必要な場合はUIとAI入力で固定補完と明示する
- proxyやestimatedを直接値へ置換しても、旧手法を残す場合は別項目として表示する
- stale cacheは利用可能性を高めるため維持するが、基準日時と経過時間を隠さない
- AI入力には、値だけでなく来歴種別、取得元、制約を渡す
