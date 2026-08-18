-- AI Investing App Supabase setup.
--
-- Run this in the Supabase SQL Editor before migrating local JSON data with:
--   python tools/migrate_to_supabase.py --execute
--
-- Supabase changed new public-schema table exposure so Data API access now
-- requires explicit grants. This app is a server-side Python/Reflex app, so the
-- default setup grants access only to service_role. Store a Supabase secret key
-- in SUPABASE_SECRET_KEY or a legacy service_role key in SUPABASE_SERVICE_ROLE_KEY
-- and do not expose it to browser-side code.

begin;

create table if not exists public.user_settings (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.portfolios (
  name text primary key,
  holdings jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.knowledge_items (
  id text primary key,
  title text not null,
  source_type text not null,
  original_content text not null,
  summary text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.trade_plans (
  id text primary key,
  ticker text not null,
  status text not null,
  entry_date date not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Transactional personal-data replacement stages rows outside the live tables.
-- The RPC is SECURITY INVOKER and executable only by service_role.
create table if not exists public.personal_data_migration_batches (
  id uuid primary key,
  requested_tables text[] not null,
  expected_counts jsonb not null,
  expected_hashes jsonb not null,
  status text not null check (status in ('staged', 'applied')),
  created_at timestamptz not null default now(),
  applied_at timestamptz
);

create table if not exists public.personal_data_migration_rows (
  batch_id uuid not null references public.personal_data_migration_batches(id) on delete cascade,
  table_name text not null,
  row_key text not null,
  payload jsonb not null,
  primary key (batch_id, table_name, row_key)
);

alter table public.user_settings enable row level security;
alter table public.portfolios enable row level security;
alter table public.knowledge_items enable row level security;
alter table public.trade_plans enable row level security;
alter table public.personal_data_migration_batches enable row level security;
alter table public.personal_data_migration_rows enable row level security;

drop policy if exists "Enable all access for all users" on public.user_settings;
drop policy if exists "Enable all access for all users" on public.portfolios;
drop policy if exists "Enable all access for all users" on public.knowledge_items;
drop policy if exists "Enable all access for all users" on public.trade_plans;

revoke all on table public.user_settings from anon, authenticated;
revoke all on table public.portfolios from anon, authenticated;
revoke all on table public.knowledge_items from anon, authenticated;
revoke all on table public.trade_plans from anon, authenticated;
revoke all on table public.personal_data_migration_batches from anon, authenticated;
revoke all on table public.personal_data_migration_rows from anon, authenticated;

grant select, insert, update, delete on table public.user_settings to service_role;
grant select, insert, update, delete on table public.portfolios to service_role;
grant select, insert, update, delete on table public.knowledge_items to service_role;
grant select, insert, update, delete on table public.trade_plans to service_role;
grant select, insert, update, delete on table public.personal_data_migration_batches to service_role;
grant select, insert, update, delete on table public.personal_data_migration_rows to service_role;

create or replace function public.apply_personal_data_migration(p_batch_id uuid)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_batch public.personal_data_migration_batches%rowtype;
  v_table text;
  v_expected integer;
  v_actual integer;
begin
  select * into v_batch
  from public.personal_data_migration_batches
  where id = p_batch_id
  for update;

  if not found or v_batch.status <> 'staged' then
    raise exception 'migration batch is missing or not staged';
  end if;

  foreach v_table in array v_batch.requested_tables loop
    if v_table not in ('user_settings', 'portfolios', 'knowledge_items', 'trade_plans') then
      raise exception 'unsupported migration table: %', v_table;
    end if;
    v_expected := (v_batch.expected_counts ->> v_table)::integer;
    select count(*) into v_actual
    from public.personal_data_migration_rows
    where batch_id = p_batch_id and table_name = v_table;
    if v_actual <> v_expected then
      raise exception 'staged row count mismatch for %: expected %, got %',
        v_table, v_expected, v_actual;
    end if;
  end loop;

  if 'user_settings' = any(v_batch.requested_tables) then
    delete from public.user_settings;
    insert into public.user_settings (key, value, updated_at)
    select payload ->> 'key', payload ->> 'value',
      coalesce((payload ->> 'updated_at')::timestamptz, now())
    from public.personal_data_migration_rows
    where batch_id = p_batch_id and table_name = 'user_settings';
  end if;

  if 'portfolios' = any(v_batch.requested_tables) then
    delete from public.portfolios;
    insert into public.portfolios (name, holdings, created_at, updated_at)
    select payload ->> 'name', coalesce(payload -> 'holdings', '[]'::jsonb),
      coalesce((payload ->> 'created_at')::timestamptz, now()),
      coalesce((payload ->> 'updated_at')::timestamptz, now())
    from public.personal_data_migration_rows
    where batch_id = p_batch_id and table_name = 'portfolios';
  end if;

  if 'knowledge_items' = any(v_batch.requested_tables) then
    delete from public.knowledge_items;
    insert into public.knowledge_items (
      id, title, source_type, original_content, summary,
      created_at, updated_at, metadata
    )
    select payload ->> 'id', payload ->> 'title', payload ->> 'source_type',
      payload ->> 'original_content', payload ->> 'summary',
      coalesce((payload ->> 'created_at')::timestamptz, now()),
      coalesce((payload ->> 'updated_at')::timestamptz, now()),
      coalesce(payload -> 'metadata', '{}'::jsonb)
    from public.personal_data_migration_rows
    where batch_id = p_batch_id and table_name = 'knowledge_items';
  end if;

  if 'trade_plans' = any(v_batch.requested_tables) then
    delete from public.trade_plans;
    insert into public.trade_plans (
      id, ticker, status, entry_date, payload, created_at, updated_at
    )
    select payload ->> 'id', payload ->> 'ticker', payload ->> 'status',
      (payload ->> 'entry_date')::date, coalesce(payload -> 'payload', '{}'::jsonb),
      coalesce((payload ->> 'created_at')::timestamptz, now()),
      coalesce((payload ->> 'updated_at')::timestamptz, now())
    from public.personal_data_migration_rows
    where batch_id = p_batch_id and table_name = 'trade_plans';
  end if;

  update public.personal_data_migration_batches
  set status = 'applied', applied_at = now()
  where id = p_batch_id;

  return jsonb_build_object('batch_id', p_batch_id, 'status', 'applied');
end;
$$;

revoke execute on function public.apply_personal_data_migration(uuid)
  from public, anon, authenticated;
grant execute on function public.apply_personal_data_migration(uuid)
  to service_role;

create or replace function public.personal_data_schema_readiness()
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $$
  with required(table_name, required_columns) as (
    values
      ('user_settings', array['key', 'value', 'updated_at']::text[]),
      ('portfolios', array['name', 'holdings', 'created_at', 'updated_at']::text[]),
      ('knowledge_items', array['id', 'title', 'source_type', 'original_content', 'summary', 'created_at', 'updated_at', 'metadata']::text[]),
      ('trade_plans', array['id', 'ticker', 'status', 'entry_date', 'payload', 'created_at', 'updated_at']::text[])
  ), checks as (
    select
      required.table_name,
      required.required_columns,
      to_regclass('public.' || required.table_name) as relation
    from required
  )
  select jsonb_build_object(
    'schema_version', 1,
    'tables', (
      select jsonb_object_agg(table_name, relation is not null) from checks
    ),
    'columns', (
      select jsonb_object_agg(
        table_name,
        coalesce(
          (
            select array_agg(column_name::text)
            from information_schema.columns
            where table_schema = 'public' and columns.table_name = checks.table_name
          ),
          array[]::text[]
        ) @> required_columns
      )
      from checks
    ),
    'grants', (
      select jsonb_object_agg(
        table_name,
        coalesce(has_table_privilege('service_role', relation, 'SELECT'), false)
        and coalesce(has_table_privilege('service_role', relation, 'INSERT'), false)
        and coalesce(has_table_privilege('service_role', relation, 'UPDATE'), false)
        and coalesce(has_table_privilege('service_role', relation, 'DELETE'), false)
        and not coalesce(has_table_privilege('anon', relation, 'SELECT'), false)
        and not coalesce(has_table_privilege('anon', relation, 'INSERT'), false)
        and not coalesce(has_table_privilege('anon', relation, 'UPDATE'), false)
        and not coalesce(has_table_privilege('anon', relation, 'DELETE'), false)
        and not coalesce(has_table_privilege('authenticated', relation, 'SELECT'), false)
        and not coalesce(has_table_privilege('authenticated', relation, 'INSERT'), false)
        and not coalesce(has_table_privilege('authenticated', relation, 'UPDATE'), false)
        and not coalesce(has_table_privilege('authenticated', relation, 'DELETE'), false)
      )
      from checks
    )
  );
$$;

revoke execute on function public.personal_data_schema_readiness()
  from public, anon, authenticated;
grant execute on function public.personal_data_schema_readiness()
  to service_role;

-- Opt existing projects into the upcoming explicit-grant behavior for new
-- public objects created by the postgres role. Supabase-managed internal roles
-- can only be adjusted by their owning role.
alter default privileges for role postgres in schema public
  revoke select, insert, update, delete on tables from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
  revoke execute on functions from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
  revoke usage, select on sequences from anon, authenticated, service_role;

alter default privileges for role postgres in schema public
  revoke execute on functions from public;

commit;
