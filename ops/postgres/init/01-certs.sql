CREATE SCHEMA IF NOT EXISTS certs;

CREATE TABLE IF NOT EXISTS certs.inventory (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  issuer        TEXT DEFAULT '',
  not_after     TIMESTAMPTZ,
  days_left     INTEGER,
  status        TEXT DEFAULT 'unknown',
  source        TEXT DEFAULT '',
  path          TEXT DEFAULT '',
  checked_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (name, source, path)
);

CREATE INDEX IF NOT EXISTS idx_certs_status ON certs.inventory (status, days_left);
CREATE INDEX IF NOT EXISTS idx_certs_checked ON certs.inventory (checked_at DESC);
