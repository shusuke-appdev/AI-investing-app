# UI監査結果

実施日: 2026-06-11 - 2026-06-12

## 対象

- ルート: `/`、`/market-watch`、`/stock`、`/portfolio`、`/knowledge`
- 画面幅: desktop `1440x900`、tablet `834x1112`、mobile `390x844`
- 監査方法: Product Designブリーフに基づく実画面確認、Browser DOM監査、スクリーンショット、Reflex production export

## 結果

| 確認項目 | 結果 |
|---|---|
| 全5ルートの表示 | 正常 |
| desktop / tablet / mobileの横方向オーバーフロー | なし |
| アクセシブル名がないボタン | 0件 |
| Browser接続エラー | なし |
| モバイル主要ナビゲーション | 左ドロワーへ変更し、5ルートと閉じる操作を確認 |
| 市場切替 | モバイルでも常時表示を維持 |
| 通常状態 | Market、Market Watchで実データ表示を確認 |
| 空状態 | Stock、Portfolio、Knowledgeで確認 |
| 読込状態 | Market、Market Watchの初期取得中表示を確認 |
| partial / stale / error | 回帰テストと共通状態表示の実装を確認。決定的なBrowser fixtureは未整備 |

詳細な機械監査値は [browser-audit.json](browser-audit.json) を参照。

## 監査中に修正した項目

- 狭幅の5項目横並びナビゲーションを左ドロワーへ変更
- テーマ切替、Market追加分析、Portfolio削除、ドロワー開閉へアクセシブル名を追加
- モバイルのナビゲーション折返しと右端余裕不足を解消

## 実行環境メモ

通常の `reflex run` は、Reflexのdisk state managerがアプリ用キャッシュディレクトリ `.states/economic_data_cache` をファイルとして削除しようとして `WinError 5` で停止した。アプリコードは変更せず、監査時のみ `REFLEX_STATES_WORKDIR=C:\tmp\ai-investing-reflex-states` を指定して起動した。
