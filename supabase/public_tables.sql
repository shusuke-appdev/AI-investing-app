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

alter table public.user_settings enable row level security;
alter table public.portfolios enable row level security;
alter table public.knowledge_items enable row level security;

drop policy if exists "Enable all access for all users" on public.user_settings;
drop policy if exists "Enable all access for all users" on public.portfolios;
drop policy if exists "Enable all access for all users" on public.knowledge_items;

revoke all on table public.user_settings from anon, authenticated;
revoke all on table public.portfolios from anon, authenticated;
revoke all on table public.knowledge_items from anon, authenticated;

grant select, insert, update, delete on table public.user_settings to service_role;
grant select, insert, update, delete on table public.portfolios to service_role;
grant select, insert, update, delete on table public.knowledge_items to service_role;

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
