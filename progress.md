# AI投資アプリ - 進捗メモ

## 最終セッション: 2026-04-29

### 完了したタスク（Reflex移行）
- [x] **Phase 1**: SPAルーティングとグローバルレイアウト構築
  - `frontend/template.py`, `frontend/components/sidebar_nav.py`
- [x] **Phase 2**: Market Intelligenceページの移植
  - `frontend/state/market_state.py`, `frontend/pages/index.py`
  - 環境スコア、AI市況レポート（Gemini）
- [x] **Phase 3**: 個別銘柄分析ページの移植
  - `frontend/state/stock_state.py`, `frontend/pages/stock.py`
  - チャート(Recharts)、テクニカル分析、AIレポート
- [x] **Phase 4**: テーマ＆ポートフォリオページの移植
  - `frontend/state/theme_state.py`, `frontend/pages/theme.py`
  - `frontend/state/portfolio_state.py`, `frontend/pages/portfolio.py`
- [x] `reflex export` で 34/34 コンパイル成功

### 設計判断メモ
- **Reflex 0.9**: `rx.Base` は廃止 → `pydantic.BaseModel` を使用
- **非同期**: `asyncio.to_thread()` + `yield` パターンで状態更新
- **ストレージ**: PortfolioStateは `storage_type` を自前で管理し、Streamlit非依存
- **型安全**: `Dict[str, Any]` では `rx.foreach` が型推論できない → 明示的なモデルクラスが必須

### 過去セッション完了分
- [x] コードベース全体の総点検（src/ 31ファイル + tests/ 8ファイル）
- [x] ruff Lintエラー 99件 → 0件に修正
- [x] pytest環境構築 + 33/33テスト全通過

### 既知の課題（未着手）
- [ ] Knowledge（知識DB）ページの移植
- [ ] チャットUI（`render_chat_component`）の各ページへの統合
- [ ] ポートフォリオのストレージタイプ選択UI
- [ ] `google.generativeai` → `google.genai` への移行（非推奨警告）

### 起動方法
```bash
# Reflexアプリ（新UI）
reflex run

# レガシーStreamlit（退避済み）
streamlit run legacy_streamlit/app.py
```
