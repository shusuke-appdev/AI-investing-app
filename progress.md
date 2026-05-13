# AI投資アプリ - 進捗メモ

## 最終セッション: 2026-05-13 (全コード総点検)
- [x] 17件のバグ修正・堅牢性改善を14ファイルに実施
- **致命的バグ修正**:
  - PCR型エラーによる天井警戒シグナル常時発火を修正 (market_analyst_service.py)
  - AI分析ボタンが ImportError で常時失敗する問題を修正 (stock_analyst.py)
  - yfinance NaN値によるフロントエンド表示崩壊を修正 (market_index_provider.py)
  - 5y期間マッピング欠落で長期MA(250/500/750日)が常に計算不能だった問題を修正 (stock_data_provider.py)
  - Reflexコンパイル時のUntypedVarError群を修正 
    - `MarketMonitorData` の型をPydantic BaseModelで厳密化しUIの属性アクセスへ変更 (market_state.py, flash_summary.py)
    - `StockState.smart_criteria` の型を `SmartCriteria` BaseModelで厳密化し、UIコンポーネントでの `ObjectItemOperation` による型エラー(`>=` 等)を解消 (stock_state.py, stock.py)
- **分析ロジック修正**: RSIゼロ除算防止強化、ボラティリティweight不均衡修正、iv変数スコープ修正
- **機能間連携**: Flash Summaryキー名修正、決算Placeholder→Finnhub委譲、query_generatorキー修正
- **堅牢性**: キャッシュメモリリーク防止、Gemini 429/503リトライ、フォールバックキャッシュ排他制御、Stooqタイムアウト
- **追加修正 (第2パス)**:
  - GARCH Mockテスト失敗を修正 — persistence変数の型ガード追加 (volatility_clustering.py)
  - オプション取得のyfinance Rate Limit対策: 期限数3に制限、期限間0.3秒・銘柄間2.0秒待機
  - オプションデータのカラム名正規化（yfinanceバージョン間差分吸収）
  - PCR/GEX計算でNaN値の安全なfillna(0)処理
  - stock.options取得のtry/except追加
- pytest 38/38 全通過

## 最終セッション: 2026-05-01 (UI改善・データ拡充)
- [x] 株式指数をETF→生指数（^GSPC, ^NDX等）に変更
- [x] 欧州（FTSE 100, DAX, CAC 40）・アジア（Hang Seng, STI）指数を追加
- [x] VIX指数を追加、米国債利回りを「株式指数・金利」パネルに統合
- [x] サイドバー上部に🇺🇸/🇯🇵市場切り替えセグメントコントロールを追加
- [x] コモディティ/仮想通貨の表示順反転（Commodity上・Crypto下）
- [x] 総合市場監視ダッシュボードを2カラム水平レイアウトに変更
- [x] オプション分析をアセットクラス別概要の下に移動
- [x] AI Market Recapボタンをヘッダーに大きめ配置
- [x] オプションデータ取得のエラーハンドリング強化
- Reflexコンパイル 38/38 成功

### 設計判断
- J-Quants: Freeプランでは指数データ取得不可 → Stooq継続
- 生指数（^始まり）はFinnhubで取得不可 → yfinanceに自動ルーティング
- オプション分析は引き続きETF（SPY, QQQ, IWM）を対象

## セキュリティ対応: 2026-05-01

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
