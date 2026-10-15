drop table if exists membership;
alter table if exists reviews_enriched drop column if exists label_config;

-- Supabase (Postgres) schema for the dashboard. Loaded by `python cli.py load-db` (offline: reads saved outputs).
-- RLS is enabled on every table with no policies: only the server-side secret key (backend) can read.
-- Business tables never contain synthetic test rows. Issue membership is reviews_enriched.issue_id
-- (one issue per complaint; the full membership.csv is in grading/). label_config is constant -> run_info.

create table if not exists run_info (
  key   text primary key,
  value jsonb not null
);

create table if not exists reviews_enriched (
  review_id        text primary key,
  source_sha256    text not null,
  review_timestamp timestamp,
  review_month     text,
  review_rating    smallint,
  app_version      text,
  status           text not null check (status in ('completed','quarantined')),
  reason           text,
  topic            text,
  area             text,
  intent           text,
  sentiment        real,
  severity         smallint,
  entities         text[],
  evidence_quote   text,
  needs_review     boolean,
  issue_id         text,
  cache_source_id  text
);
create index if not exists reviews_enriched_issue on reviews_enriched (issue_id);
create index if not exists reviews_enriched_topic_intent on reviews_enriched (topic, intent);

create table if not exists issues (
  issue_id        text primary key,
  rank            integer not null,
  topic           text not null,
  subtopic        text not null,
  area            text not null,
  name            text,
  description     text,
  complaint_count integer not null,
  severity_sum    integer not null,
  mean_severity   text not null,      -- 6 dp, decimal half-up (contract), kept as text to avoid float drift
  priority_score  integer not null,
  example_ids     text[]
);

create table if not exists claims (
  claim_id text primary key,
  issue_id text not null,
  metric   text not null,
  value    text not null,
  source   text not null
);

create table if not exists recommendations (
  id                serial primary key,
  run_id            text not null,
  created_at        timestamptz not null default now(),
  generator         text not null,     -- model + effort + prompt version
  recommended_area  text not null,
  headline          text not null,
  memo_markdown     text not null,
  items             jsonb not null,    -- structured recommendations with issue/claim/review IDs
  evidence          jsonb not null,    -- bounded evidence pack (review_id, issue_id, quote)
  check_status      text not null      -- code claim-check result
);

alter table run_info         enable row level security;
alter table reviews_enriched enable row level security;
alter table issues           enable row level security;
alter table claims           enable row level security;
alter table recommendations  enable row level security;

-- Explicit privileges ("automatically expose new tables" is off): only the backend's secret key (service_role)
-- may read; the public anon/authenticated roles get nothing.
grant usage on schema public to service_role;
grant select on run_info, reviews_enriched, issues, claims, recommendations to service_role;
revoke all on run_info, reviews_enriched, issues, claims, recommendations from anon, authenticated;
