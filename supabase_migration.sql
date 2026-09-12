-- SmartPostAI minimal schema for hackathon (free mode)
-- Safe to run multiple times

-- Extensions (gen_random_uuid)
create extension if not exists "pgcrypto";

-- Generated posts (AI drafts)
create table if not exists public.generated_posts (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  topic text,
  content text,
  hashtags jsonb default '[]'::jsonb,
  image_url text,
  source_url text,
  linkedin_post_url text,
  linkedin_post_id text,
  language text default 'en',
  created_at timestamptz default now()
);

-- Scheduled posts
create table if not exists public.scheduled_posts (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  platform text default 'linkedin',
  content text not null,
  cron_expression text,
  scheduled_at timestamptz,
  status text default 'pending',
  image_url text,
  post_url text,
  post_id text,
  posted_at timestamptz,
  review_token text,
  team_emails jsonb,
  approved_emails jsonb,
  review_comments text,
  created_at timestamptz default now()
);

-- LinkedIn OAuth tokens
create table if not exists public.linkedin_connections (
  id uuid primary key default gen_random_uuid(),
  user_id text unique not null,
  access_token text,
  refresh_token text,
  expires_at timestamptz,
  profile_id text,
  profile_name text,
  profile_email text,
  profile_picture text,
  created_at timestamptz default now()
);

-- Post templates
create table if not exists public.post_templates (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  name text not null,
  content text not null,
  description text,
  variables jsonb default '[]'::jsonb,
  created_at timestamptz default now()
);

-- Payments (optional; present to avoid analytics errors even in free mode)
create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  tx_hash text,
  service text,
  amount text,
  status text default 'verified',
  from_address text,
  created_at timestamptz default now(),
  updated_at timestamptz
);

-- Public images bucket for uploaded/generated images
insert into storage.buckets (id, name, public)
values ('images','images', true)
on conflict (id) do nothing;

-- Allow public read access to the images bucket
drop policy if exists "Public read access to images" on storage.objects;
create policy "Public read access to images" on storage.objects
for select
using (bucket_id = 'images');
