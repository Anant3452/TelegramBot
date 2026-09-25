-- Run once in Supabase > SQL Editor.
-- Nothing is ever deleted: rejected notes and rejected drafts are kept as a
-- record of what needs improving.

create table if not exists notes (
  id                  bigint generated always as identity primary key,
  created_at          timestamptz not null default now(),
  telegram_update_id  bigint unique,          -- dedupes Telegram webhook retries
  chat_id             bigint not null,
  message_id          bigint,
  source              text not null default 'text',   -- text | voice
  text                text not null,
  score               int,
  score_reason        text,
  status              text not null default 'received', -- received | rejected | drafted | error
  error               text
);

create table if not exists drafts (
  id                    bigint generated always as identity primary key,
  created_at            timestamptz not null default now(),
  note_id               bigint references notes(id),
  chat_id               bigint not null,
  body                  text not null,
  provider              text,                 -- gemini | claude
  model                 text,
  search_phrase         text,
  used_news             boolean not null default false,
  news_headline         text,
  news_source           text,
  news_date             text,
  news_link             text,
  telegram_message_ids  bigint[] not null default '{}',
  status                text not null default 'pending'
                        check (status in ('pending', 'approved', 'rejected')),
  decided_at            timestamptz
);

create table if not exists voice_skill (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  content     text not null,
  active      boolean not null default true
);

create index if not exists drafts_chat_status_idx on drafts (chat_id, status, created_at desc);

-- Lock the tables to the service_role key the bot uses; the public anon key gets nothing.
alter table notes       enable row level security;
alter table drafts      enable row level security;
alter table voice_skill enable row level security;
