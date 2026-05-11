-- Extensions used by the AMI Trade schema.
-- Runs once on first postgres container start (via docker-entrypoint-initdb.d).

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- alternative uuid generation
