# 市場監視・予測の役割分担

更新日: 2026-07-14

## 基本原則

市場監視は「現在どのような状態か」を説明し、短期予測は「将来分布が検証に耐えるか」を扱います。両者を一つの総合確率へ混ぜません。詳細な入出力は [分析・予測機能カタログ](ANALYSIS_FEATURE_CATALOG.md) を正本とします。

## レイヤー別の責務

| レイヤー | 主な問い | 出力 | 他機能へ影響してよい範囲 |
|---|---|---|---|
| 市場サマリー | 主要資産は今どう動いたか | 価格・騰落・為替 | 観測値として共有 |
| Market Monitoring | トレンド、breadth、flow、信用、vol、option需給はどの状態か | `evaluation`、regime、risk signposts | 定性状態とリスク姿勢 |
| 短期市場予測 | SPY/QQQの1・5・20営業日分布はOOS検証を通るか | 確率、分位点、検証指標、地平別status | `validated`の対応地平だけ1W/1M見通しへ反映 |
| 複合センチメント | tail、PCR、Gamma、breadthが共同で警戒状態か | state、risk floor、根拠 | リスク維持・引上げだけ。確率変更と格上げは禁止 |
| Stock確率シグナル | 個別株の類似局面はどう分布したか | 5日期待値、上昇率、20日超過、配分上限 | Stock内だけ。市場ガードレールはdowngrade-only |
| Portfolio | 保有資産の構成・集中・通貨リスクは何か | 円換算総額、通貨小計、構成比、露出 | 資産配分の表示。MarketContextは為替・市場文脈として再利用 |

## 更新順とデータ再利用

詳細更新は次の順序です。

1. `Theme/Flow`: 現在状態、IBD式proxy、マイクロストラクチャー、テーマ・flow
2. `Credit/Risk`: 信用ストレス、市場歪み、リスク兆候
3. `Vol/Sentiment`: 更新済み信用ストレスを使うvolレジーム、短期予測、複合状態
4. `Options`: 明示操作でoption chainを取得し、同じチェーンで市場構造・見通し・複合状態を再計算

Theme/Flowのマイクロストラクチャーはoption chainを暗黙取得しません。Options更新後だけ、取得済みSPY optionを使ってVRP等を更新します。重要水準と市場ドライバーは同一更新内で再利用します。

## 短期市場予測

- 対象: SPY、QQQの1・5・20営業日
- 入力: 価格・出来高、breadth、相対強弱、Cboe指数群、20日モデルだけ公表遅延を適用したCFTC TFF
- 方法: train-only変換、ridge logistic、trend、時間を空けた類似局面のensemble
- 検証: Brier skill、log loss、ECE、80%区間coverage、類似事例数を地平ごとに判定
- 利用制約: `research_only`、stale、unavailableは表示限定。別地平の合格を流用しない

予測値は確定的な売買シグナルではありません。`market_timeframes`は入力の`status`と`coverage`を併記し、利用可能な根拠がゼロなら「レンジ」ではなく「判定不能」とします。

## 複合センチメント

`composite_sentiment`は別の上昇確率ではなく、説明可能な共同状態分類です。主に次を組み合わせます。

- VIX水準・変化、VVIX、SKEW、VIX期間構造
- OCC SPY/QQQ日次Put/Callの履歴percentile
- 完全な直接GammaとGamma転換
- RSP/SPY、IWM/SPYによるbreadth

ルールに必要な条件がすべてcurrentかつ利用可能な場合だけ`confirmed`です。OCC履歴不足、proxy/incomplete Gamma、stale、breadth欠損は`partial`または`unavailable`で、risk floorを拘束的に使いません。`refresh_occ=False`の再計算では保存済みOCC履歴を読み、空の履歴へ戻しません。

## Stockとの境界

- `StockSignalContext`はテクニカル、Entry、確率、Trend Follow、FOMO、ファンダメンタル、テーマ、根拠一致度、日本株需給を保持します。
- 各診断は異なる問いに答え、単一の重複スコアへ統合しません。
- 類似事例0件は期待値・上昇率を`None`とし、0%と表示しません。
- 1–29件はLow confidenceかつ最大配分0%です。
- benchmark欠損は20日超過だけを算出不可にし、絶対5日期待値まで破棄しません。
- volまたは必須入力欠損はリスク調整値を算出せず、Watch/0%です。
- US市場ガードレールはStock姿勢を悪化させる方向だけに作用し、日本株には適用しません。

## 直接データとproxy

- IBD式市場状態はSPY/NDX OHLCVによるfree-data proxyです。
- CTAポジショニングとAmihud流動性はproxyで、CFTC実建玉や実板ではありません。
- ETFリーダーシップとセクターflowはissuer-reported fund flowではありません。
- MarketData.app/yfinanceのGamma符号は実ディーラー建玉を直接観測したものではありません。
- Cboe指数、CFTC公表系列、OCC集計は直接データですが、公表時刻・鮮度・観測数の制約を保持します。

## 公式データ参照先

- Cboe index history: `https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYMBOL>_History.csv`
- CFTC TFF API: `https://publicreporting.cftc.gov/resource/gpe5-46if.json`
- OCC option volume query: `https://marketdata.theocc.com/volume-query`
