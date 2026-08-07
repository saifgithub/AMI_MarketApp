-- CR124/M8 — the marketing API gets its own low-privilege role.
--
-- Before this, `api-website` connected as the Postgres SUPERUSER, so any RCE in
-- the public marketing container was a direct pivot into the app database:
-- users, magic-link challenges, mandates, journals. The two databases live in
-- one cluster, so "different database" was never a boundary on its own — the
-- role is.
--
-- Runs once on FIRST container start (docker-entrypoint-initdb.d). melehost's
-- `postgres_data` volume already exists, so this file will NOT run there; the
-- same statements are applied by hand in infra/CR124_HARDENING_RUNBOOK.md
-- step 3. Keep the two in sync.
--
-- WEBSITE_DB_PASSWORD is substituted by the runbook, not by Postgres — this
-- file is only reachable on a fresh volume, where the placeholder below is
-- replaced before the volume is created.

CREATE DATABASE ami_website;

CREATE ROLE ami_website WITH LOGIN PASSWORD 'CHANGE_ME_SEE_RUNBOOK';

-- Owns its own database and nothing else. No superuser, no createdb, no
-- createrole, and explicitly no access to `ami_trade`.
ALTER DATABASE ami_website OWNER TO ami_website;
REVOKE ALL ON DATABASE ami_trade FROM ami_website;
REVOKE ALL ON DATABASE ami_website FROM PUBLIC;

-- PUBLIC can connect to any database by default; that is what makes a
-- second role meaningless unless revoked.
REVOKE CONNECT ON DATABASE ami_trade FROM PUBLIC;
GRANT CONNECT ON DATABASE ami_website TO ami_website;
