CREATE SCHEMA IF NOT EXISTS mentions;

CREATE TABLE IF NOT EXISTS mentions.items (
  id            BIGSERIAL PRIMARY KEY,
  slack_ts      TEXT NOT NULL,
  channel_id    TEXT NOT NULL DEFAULT '',
  channel_name  TEXT NOT NULL DEFAULT '',
  permalink     TEXT NOT NULL DEFAULT '',
  author_id     TEXT NOT NULL DEFAULT '',
  author_name   TEXT NOT NULL DEFAULT '',
  mention_type  TEXT NOT NULL DEFAULT 'user', -- team|user
  mentioned_id  TEXT NOT NULL DEFAULT '',
  mentioned     TEXT NOT NULL DEFAULT '',
  text_full     TEXT NOT NULL DEFAULT '',
  text_short    TEXT NOT NULL DEFAULT '',
  keywords      TEXT[] NOT NULL DEFAULT '{}',
  msg_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  day           DATE NOT NULL DEFAULT CURRENT_DATE,
  UNIQUE (slack_ts, channel_id, mentioned_id)
);

CREATE INDEX IF NOT EXISTS idx_mentions_day ON mentions.items (day DESC, msg_at DESC);
CREATE INDEX IF NOT EXISTS idx_mentions_who ON mentions.items (mentioned, day DESC);
CREATE INDEX IF NOT EXISTS idx_mentions_kw  ON mentions.items USING GIN (keywords);

CREATE TABLE IF NOT EXISTS mentions.keywords (
  id    SERIAL PRIMARY KEY,
  word  TEXT UNIQUE NOT NULL,
  kind  TEXT NOT NULL DEFAULT 'service' -- project|service|entity
);

INSERT INTO mentions.keywords (word, kind) VALUES
 ('Wildfire','service'),('Gwildfire','service'),('Swildfire','service'),
 ('StarAds','service'),('Vidmind','project'),('KSTV','project'),
 ('CloudFront','entity'),('HLS','entity'),('SCTE-35','entity'),
 ('OnCall','service'),('Postgres','entity'),('Redis','entity')
ON CONFLICT (word) DO NOTHING;

CREATE TABLE IF NOT EXISTS mentions.roster (
  slack_id   TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  username   TEXT NOT NULL DEFAULT '',
  is_team    BOOLEAN NOT NULL DEFAULT FALSE
);
