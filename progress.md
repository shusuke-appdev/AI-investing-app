# AI投資アプリ - 進捗メモ

## 最終セッション: 2026-04-19

### 完了したタスク
- [x] コードベース全体の総点検（src/ 31ファイル + tests/ 8ファイル）
- [x] ruff Lintエラー 99件 → 0件に修正
- [x] pytest環境構築 + 33/33テスト全通過
- [x] conftest.pyにオプショナル依存パッケージのモック注入（openbb, edinet_tools, arch, finnhub, gnews）
- [x] bare except → 具体的例外型に修正（jquants_client.py）
- [x] E402（インポート順）修正（settings_storage.py）
- [x] SIM102（ネストif）修正（stock_data_provider.py）
- [x] E701（1行複数文）修正（market_microstructure.py, jquants_client.py）

### 既知の課題（未着手）
- [ ] `portfolio_input.py` (525行) のコンポーネント分割
- [ ] `option_analyst.py` (457行) のユーティリティ分離
- [ ] `app.py` / `sidebar.py` の設定ロード二重化解消
- [ ] `stock_data_provider.py` のプレースホルダー関数（earnings_calendar等）の実装
- [ ] `google.generativeai` → `google.genai` への移行（非推奨警告）
- [ ] `themes_config.py` の `src/` 配下への移動
- [ ] `utils/` ディレクトリの命名改善

### 設計メモ
- J-Quants Freeプランの92日遅延は仕様。コメントを明確化済み。
- DataProviderはFacade + static methods + グローバル変数パターン。テスト時はDIで切替可能。
