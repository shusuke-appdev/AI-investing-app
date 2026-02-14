# ユーザーアクションプラン: SBI証券連携機能の有効化

現在、AIによる「仕組みの実装」は完了しました。
残るは、あなたのPC環境（Windows + HYPER SBI 2）で実際に動かすための「現地調整」です。

以下の手順を1つずつ順番に実行してください。

## Step 1: 認証情報の入力

1.  **エクスプローラー** または **VS Code** で以下のファイルを開きます。
    `c:\Users\shusk\.gemini\antigravity\workspace\AI-investing-app\tools\sbi_sync\.env`
2.  以下の項目をご自身のログイン情報に書き換えてください。
    ```env
    SBI_USER="あなたのユーザーネーム"
    SBI_PASSWORD="あなたのログインパスワード"
    ```
    ※ `SUPABASE_URL` と `SUPABASE_KEY` は既に入力済みですので、そのままでOKです。

## Step 2: 動作確認（初回実行）

1.  **HYPER SBI 2 を起動** し、ログイン状態にしてください。
    - **重要:** 起動していないと接続に失敗します。
2.  **ターミナル**（PowerShell または コマンドプロンプト）を開き、以下のコマンドを実行します。
    ```powershell
    cd c:\Users\shusk\.gemini\antigravity\workspace\AI-investing-app\tools\sbi_sync
    .venv\Scripts\python main.py
    ```
3.  **ログを確認** します。
    - 成功時: `INFO: Connected to HYPER SBI 2` と表示されます。
    - 失敗時: `ERROR: Failed to connect...` と表示されます。

## Step 3: コードの微調整（GUI操作）

もし Step 2 でエラーが出た場合、または「保有証券の取得に失敗」した場合は、`sbi_client.py` の調整が必要です。
これは、お使いのPCのディスプレイ解像度やウィンドウ配置によって、ボタンの位置などが微妙に異なるためです。

1.  `tools/sbi_sync/sbi_client.py` を開きます。
2.  **接続処理 (`connect`) の調整**:
    - `title_re=".*HYPER SBI 2.*"` という部分でウィンドウを探しています。
    - もしウィンドウが見つからない場合、正規表現 (`.*`) を調整するか、正確なタイトルを入力してください。
3.  **操作処理 (`get_portfolio`) の調整**:
    - 現在のコードは「雛形」です。
    - 実際にタブをクリックするには、`inspect.exe` (Windows SDKに含まれるツール) などを使って、ボタンの識別子（AutomationId や Name）を調べる必要があります。
    - **難しい場合**: 一旦 `main.py` を動かしたままにし、HYPER SBI 2 の画面を手動で「保有証券」タブに切り替えてから実行してみてください（コードによってはアクティブな画面からデータを読むだけの作りも可能です）。

## Step 4: 常駐化 (運用開始)

正常に動くようになったら、PCを使っている間はこの `main.py` を起動したままにしておきます。
- 1分ごとに株価をチェックし、Supabaseへ送信します。
- 5分ごとにポートフォリオを同期します。
- スマートフォン等からアプリを見ると、最新のデータが反映されているはずです。

### 困ったときは？
- ログファイル `sbi_sync.log` にエラー詳細が出力されています。これを確認してください。
