# テスト体系

`test_inventory.toml` が、全 `test_*.py` の担当領域・性質・データの現実性・信頼度・限界・実行プロファイルを一度だけ登録する正本です。`test_inventory_contract.py` は、実ファイルとの欠落・重複を検出します。

## 分類

| 分類 | 主な保証 | 主な限界 |
| --- | --- | --- |
| 定量計算 | 数式、時系列整合、検証ゲート | 将来の投資成果は保証しない |
| 外部provider契約 | 認証、応答正規化、欠損・エラー、キャッシュ | 実APIの稼働や将来の仕様変更は保証しない |
| Market統合 | 市場コンテキスト、テーマ・フロー、戦略の統合 | 外部取得と実ブラウザ操作は含まない |
| Stock/売買分析 | 銘柄分析、Option、根拠一致度、売買分析 | 実注文・約定・収益は対象外 |
| 保存・セキュリティ | 保存先、権限、秘密情報、移行 | 本番Supabase権限は手動live smokeで確認する |
| Frontend state/UI | 状態遷移、表示契約、静的HTML | 動的E2Eと視覚差分は手動確認する |
| live smoke契約 | 必須フラグとPASS/FAIL/SKIP判定 | 実API確認そのものは標準pytestに含めない |

## 実行プロファイル

```powershell
# 編集中の短時間ゲート: integration / slow を除外
.\.venv\Scripts\python.exe scripts\check.py --quick

# 完全リリースゲート
.\.venv\Scripts\python.exe scripts\check.py

# 完全ゲート + src/frontend のbranch coverage可視化
.\.venv\Scripts\python.exe scripts\check.py --coverage
```

`--coverage` は `.states/.coverage`、`.states/coverage.json`、`.states/coverage_html/` を生成します。2026-07-14の初回branch coverage 62.9%を切り捨てた62%を最低率とし、重要経路のテストが減った場合にCIを失敗させます。閾値は今後の成功ベースラインに合わせて上げ、下げません。

全プロファイルで、provider結果、共有分析コンテキスト、Theme契約、UI用エラー契約の段階的mypy検査も実行します。動的なReflexコード全体を一度に厳格化せず、UI・AI・戦略を横断する契約から対象を広げます。

CIではReflex export後にChromiumを使い、390×844と1280×720で主要5ルートの横スクロール、モバイルドロワーのフォーカス移動とEscape操作を確認します。ローカルで再現する場合は `python -m playwright install chromium` の後に `python scripts/ui_browser_smoke.py` を実行します。

## マーカーと外部境界

- `contract`: provider、保存、live smokeなどの境界契約
- `integration`: 複数サービスまたはFrontend stateの統合
- `slow`: 高計算量または実スレッドを使う検証
- 純粋な短時間単体テストは無印

マーカーは台帳から収集時に付与します。Finnhub、Gemini、Supabase、保存先のモックは明示的fixtureであり、依存するテストが引数または `usefixtures` で宣言します。全テスト共通のautouseは安全な `APP_MODE=private` だけです。

実APIの生存確認は `scripts/live_smoke.py` に集約しています。外部APIの生存と、計算・契約の正しさは別のテスト層として扱います。
