# Tasks

- [x] Python実行環境を復旧し、`python -m pytest -q` と `python -m compileall src frontend tests` を通す <!-- id: 1 -->
- [x] `ruff check . --fix` と `ruff format .` を適用し、自動修正後に残る指摘をレビューする <!-- id: 2 -->
- [x] GitHub Actions に lint / test / compile ジョブを追加し、Hugging Face 同期を品質チェック成功後に限定する <!-- id: 3 -->
- [ ] Reflex を現行UIの正本として、Streamlit残存コードの扱いを決める <!-- id: 4 -->
- [ ] Market / Stock / Portfolio / Knowledge の表示モデルとユースケース出力モデルを定義する <!-- id: 5 -->
- [ ] 外部API取得結果に `source`、`fetched_at`、`is_stale`、`error` を持つ共通ステータスを導入する <!-- id: 6 -->
- [ ] `frontend/state/market_state.py` の業務ロジックを `src/services/market_dashboard_service.py` へ移す <!-- id: 7 -->
- [ ] `frontend/state/stock_state.py` の業務ロジックを `src/services/stock_dashboard_service.py` へ移す <!-- id: 8 -->
- [ ] `frontend/state/portfolio_state.py` の業務ロジックを `src/services/portfolio_dashboard_service.py` へ移す <!-- id: 9 -->
- [ ] オプション分析を「取得」と「計算」に分離し、取得失敗・推定値・キャッシュ値をUIに表示する <!-- id: 10 -->
- [ ] AI分析用の `AnalysisContext` を導入し、欠損データと取得元をプロンプトに明示する <!-- id: 11 -->
- [ ] local / GAS / Supabase の保存スキーマをPydanticモデルで固定し、保存前後の検証を追加する <!-- id: 12 -->
- [ ] 参照知識DBに重複排除、鮮度表示、プロンプト注入対策を追加する <!-- id: 13 -->
- [ ] 生成物、SQLiteキャッシュ、アップロードファイル、zip成果物のGit管理方針を整理する <!-- id: 14 -->
- [ ] 主要画面のスモークテストを追加する <!-- id: 15 -->
