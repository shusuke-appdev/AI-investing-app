# Supabase Data API grants

## 背景

Supabase は、2026-05-30 から新規プロジェクトで `public` スキーマの新規テーブルを Data API / GraphQL API に自動公開しない既定に変更します。既存プロジェクトでも 2026-10-30 以降、新しく作成する `public` テーブルには明示的な `GRANT` が必要です。

このアプリは Supabase Python client から PostgREST/Data API を使い、以下の3テーブルを参照します。

- `public.user_settings`
- `public.portfolios`
- `public.knowledge_items`

## 対応方針

このリポジトリでは、テーブル作成、不要な permissive RLS policy の削除、Data API 用の明示 `GRANT`、および `postgres` ロールが今後作る `public` オブジェクトの自動公開抑止を [supabase/public_tables.sql](../supabase/public_tables.sql) にまとめています。新規 Supabase プロジェクトを作る場合、または上記テーブルを作り直す場合は、データ移行前に Supabase SQL Editor でこの SQL を実行してください。

```powershell
python tools/migrate_to_supabase.py --print-setup-sql
```

表示された SQL を Supabase SQL Editor に貼り付けて実行します。その後、ローカルJSONを移行する場合のみ以下を実行します。

```powershell
python tools/migrate_to_supabase.py --execute
```

既存テーブルを消して入れ替える場合だけ、事前バックアップ付きで以下を使います。

```powershell
python tools/migrate_to_supabase.py --execute --confirm-destroy
```

## キーの扱い

このアプリの Supabase アクセスはサーバー側 Python/Reflex から行われます。新規設定では `SUPABASE_SECRET_KEY` をサーバー環境変数として設定する方針です。これはブラウザやクライアント側コードに出してはいけません。

互換性のため `SUPABASE_SERVICE_ROLE_KEY` と `SUPABASE_KEY` も引き続き読みますが、新規プロジェクトでは `SUPABASE_SECRET_KEY` を優先してください。

```env
SUPABASE_URL=your_supabase_url_here
SUPABASE_SECRET_KEY=your_supabase_secret_key_here
```

公開可能な anon/publishable key でこのアプリから直接書き込みたい場合は、`anon` / `authenticated` への `GRANT` と RLS policy を別途明示してください。現在の既定 SQL は、誤公開を避けるため `service_role` のみに Data API 権限を付与します。

## 既存プロジェクトで確認すること

既存テーブルの現在の権限は今回の変更では即時削除されません。ただし、2026-10-30 以降に新規作成するテーブルは明示 `GRANT` がないと Data API から見えません。

Supabase Dashboard の Security Advisor で Data API に公開されているテーブルを確認してください。SQL で確認する場合は以下を使えます。

```sql
select
  c.relname as table_name,
  c.relrowsecurity as rls_enabled,
  g.grantee,
  g.privilege_type
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
left join information_schema.role_table_grants g
  on g.table_schema = n.nspname
 and g.table_name = c.relname
 and g.grantee in ('anon', 'authenticated', 'service_role')
where n.nspname = 'public'
  and c.relkind = 'r'
  and c.relname in ('user_settings', 'portfolios', 'knowledge_items')
order by c.relname, g.grantee, g.privilege_type;
```

`service_role` に `SELECT` / `INSERT` / `UPDATE` / `DELETE` があり、`anon` / `authenticated` に Data API 用の操作権限がなく、各テーブルで RLS が有効なら、このリポジトリの標準構成と一致しています。

Security Advisor に `RLS Enabled No Policy` が INFO として出る場合があります。このアプリの標準構成では、公開クライアントから直接テーブルを触らず、サーバー側 secret key / service role だけでアクセスするため、RLS policy なしは意図した状態です。`RLS Policy Always True` が出る場合は、`Enable all access for all users` のような常時 true policy を削除してください。
