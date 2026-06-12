# コード点検結果

点検日: 2026-05-14

## 実施内容

- リポジトリ構成、依存関係、起動入口、既存資料を確認
- Reflex UI、旧Streamlit UI、分析ロジック、データ取得、保存層を横断確認
- `ruff check .` と `ruff format --check .` を実行
- `.venv` の Python 起動不全を復旧し、通常の `.venv\Scripts\python.exe` から検証を実行

## 概要評価

このアプリは、投資調査に必要な機能が広く実装されています。一方で、Reflex移行の途中状態が残っており、実行入口、UI正本、保存契約、外部API失敗時の扱い、AI入力データの検証可能性が弱い状態です。

単なる整形や小規模リファクタリングよりも、まず「現行機能を落とさずに境界を明確化する」改修が必要です。

## 重大度別の指摘

### Resolved: 実行環境が再現できない

- 旧現象: `python` が PATH に存在せず、`.venv\Scripts\python.exe` も起動不可
- 原因: 仮想環境が存在しない Python インストール先を参照していた
- 対応: Python 3.12.10 (`C:\tmp\Python312\python.exe`) で `.venv` を再作成し、`pip`、`pytest`、`ruff`、主要依存関係を `requirements.txt` から入れ直した
- 補足: `py -3.12` は復旧済み。`python` はユーザーPATHに登録済みで、新しく開いたターミナルから解決される

### Critical: README が現行実装と不一致だった

- 旧状態: README は Streamlit の `streamlit run app.py` を案内していた
- 現行実装: `frontend/frontend.py` を入口にした Reflex アプリ
- 影響: 初回セットアップ、Hugging Face Spaces、開発者オンボーディングが失敗する
- 対応: README を Reflex 正本に更新済み

### Major: Reflex UI と Streamlit UI が並存し、正本が不明確

- 該当: `frontend/`、`src/ui/`、`legacy_streamlit/`
- 影響: 同じ機能を二重に直す必要が出る。将来のバグ修正が片側にだけ入りやすい
- 対応方針: `frontend/` を正本に固定し、`src/ui/` は deprecated として凍結または段階削除する

### Major: UI state がユースケース調整と表示整形を抱え込みすぎている

- 該当: `frontend/state/market_state.py`、`frontend/state/stock_state.py`、`frontend/state/portfolio_state.py`
- 影響: 外部API失敗、データ整形、UIメッセージ、並行実行が1クラスに混在し、テストが難しい
- 対応方針: `src/services/*` にユースケースを寄せ、state は入力・出力・状態遷移に限定する

### Major: 外部API失敗時の状態が曖昧

- 該当: `src/finnhub_client.py`、`src/stock_data_provider.py`、`src/option_data_provider.py`、`src/news_aggregator.py`
- 現状: `except Exception` でログ出力後に `None` / 空配列 / 0.0 を返す箇所が多い
- 影響: 「市場が中立」なのか「データが取れていない」のかがUIとAIプロンプトで混ざる
- 対応方針: `DataResult` のような成功・失敗・鮮度・ソースを持つ戻り値へ段階移行する

### Major: AIレポート生成の入力契約が弱い

- 該当: `src/services/market_analyst_service.py`、`src/stock_analyst.py`、`src/prompts/analysis_prompts.py`
- 影響: 欠損データや古いデータが、プロンプト上で自然文に混ざり検証しづらい
- 対応方針: AIへ渡す前に、構造化された `AnalysisContext` を作り、欠損・推定値・取得元を明示する

### Major: 保存層の抽象化はあるがスキーマ契約が不足

- 該当: `src/storage/base.py`、`src/portfolio_storage.py`、`src/knowledge_storage.py`
- 影響: local / Supabase 間でデータ形状がずれたときに検出しづらい
- 対応方針: PydanticモデルまたはTypedDictを保存契約として定義し、保存前後のバリデーションを追加する

### Resolved: CI が品質確認を実行してからデプロイ同期する構成へ更新

- 該当: `.github/workflows/sync_to_hub.yml`
- 旧状態: main/master push で Hugging Face Spaces に force push
- 対応: `ruff check`、`ruff format --check`、`compileall`、`pytest` の成功後に同期するよう更新
- 補足: PR と feature branch push 用に `.github/workflows/ci.yml` を追加

### Resolved: ruff 指摘は解消済み

- 初回確認時は `ruff check .` で70件、`ruff format --check .` で54ファイル未整形を検出
- 自動修正と最小手動修正により、`ruff check .` と `ruff format --check .` は通過済み
- 主な修正内容: import順、空白行、未使用変数、不要なf-string、テストの未使用import

### Minor: 環境変数テンプレートが不足していた

- 旧状態: `.env.example` は Gemini と J-Quants のみ
- 実コード: Finnhub、EDINET、Supabaseも利用
- 対応: `.env.example` を更新済み

## 機能面のリスク

- Market Intelligence は並行取得化されているが、データソースごとの失敗と鮮度がUIに十分出ていない
- オプション分析は yfinance / Finnhub の制限に強く依存するため、レート制限時の再試行・バックオフ・部分表示が重要
- 日本株分析は J-Quants / EDINET / yfinance / Stooq の補完関係が複雑で、取得元優先順位の仕様化が必要
- 参照知識はAI品質に直結するため、重複、古い情報、プロンプト注入への対策が必要
- ポートフォリオ保存はローカルJSONでは扱いやすいが、Supabase移行時にスキーマ差異が見えにくい

## 検証結果

```text
.\.venv\Scripts\python.exe -m compileall src frontend tests
結果: 通過。

.\.venv\Scripts\python.exe -m pytest -q
結果: 38 passed。

.\.venv\Scripts\ruff.exe check .
結果: 通過。

.\.venv\Scripts\ruff.exe format --check .
結果: 通過。
```

## 優先結論

1. 復旧した実行環境を前提に、テストと構文チェックを継続的に維持する
2. Reflexを現行正本として資料・起動・CIを揃える
3. データ取得結果の成功・失敗・鮮度を構造化し、UIとAIに同じ契約で渡す
4. Streamlit残存コードを凍結または移行完了として整理する
5. AIレポート生成の前段に、検証可能な分析コンテキストを導入する
