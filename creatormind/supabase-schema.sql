-- Run this in your Supabase SQL editor

create extension if not exists "pgcrypto";

create table public.creators (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade unique,
  channel_url           text,
  channel_id            text,
  channel_name          text,
  channel_description   text,
  subscriber_count      int,
  total_videos          int,
  top_videos            jsonb default '[]',
  niche                 text,
  content_pillars       text[] default '{}',
  target_audience       text,
  creator_voice         text,
  strength_topics       text[] default '{}',
  avoid_topics          text,
  content_style         text,
  unique_angle          text,
  goals                 text,
  story                 text,
  inspirations          text,
  posting_frequency     text,
  biggest_challenge     text,
  style_words           text,
  stripe_customer_id    text,
  stripe_subscription_id text,
  status                text default 'trial' check (status in ('trial','active','cancelled')),
  profile_built         boolean default false,
  created_at            timestamptz default now()
);

create table public.video_ideas (
  id                uuid primary key default gen_random_uuid(),
  creator_id        uuid not null references public.creators(id) on delete cascade,
  title             text not null,
  hook              text not null,
  description       text,
  thumbnail_concept text,
  format            text,
  viral_score       int check (viral_score between 1 and 100),
  trend_source      text,
  trend_url         text,
  why_now           text,
  estimated_views   text,
  status            text default 'new' check (status in ('new','saved','dismissed','used')),
  week_of           date,
  created_at        timestamptz default now()
);

create table public.pivot_opportunities (
  id                uuid primary key default gen_random_uuid(),
  creator_id        uuid not null references public.creators(id) on delete cascade,
  niche             text not null,
  rationale         text not null,
  example_channels  jsonb default '[]',
  difficulty        text check (difficulty in ('easy','medium','hard')),
  revenue_potential text,
  week_of           date,
  created_at        timestamptz default now()
);

create table public.weekly_briefs (
  id                uuid primary key default gen_random_uuid(),
  creator_id        uuid not null references public.creators(id) on delete cascade,
  week_of           date not null,
  summary           text not null default '',
  top_trend         text,
  calendar          jsonb default '[]',
  format_to_steal   text,
  platform_insight  text,
  email_sent        boolean default false,
  created_at        timestamptz default now(),
  unique (creator_id, week_of)
);

create table public.scout_runs (
  id                uuid primary key default gen_random_uuid(),
  creator_id        uuid not null references public.creators(id) on delete cascade,
  sources_checked   int default 0,
  ideas_generated   int default 0,
  error             text,
  created_at        timestamptz default now()
);

create index on public.video_ideas(creator_id, viral_score desc);
create index on public.video_ideas(creator_id, week_of desc);
create index on public.weekly_briefs(creator_id, week_of desc);
create index on public.scout_runs(creator_id, created_at desc);

alter table public.creators             enable row level security;
alter table public.video_ideas          enable row level security;
alter table public.pivot_opportunities  enable row level security;
alter table public.weekly_briefs        enable row level security;
alter table public.scout_runs           enable row level security;

create policy "users own their creator profile" on public.creators
  for all using (auth.uid() = user_id);
create policy "users own their ideas" on public.video_ideas
  for all using (creator_id in (select id from public.creators where user_id = auth.uid()));
create policy "users own their pivots" on public.pivot_opportunities
  for all using (creator_id in (select id from public.creators where user_id = auth.uid()));
create policy "users own their briefs" on public.weekly_briefs
  for all using (creator_id in (select id from public.creators where user_id = auth.uid()));
create policy "users own their scout runs" on public.scout_runs
  for all using (creator_id in (select id from public.creators where user_id = auth.uid()));
