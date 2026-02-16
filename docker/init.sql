-- init.sql

-- SQL ist nur für verwaltungsstuff

-- Jobs table
DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs (
    job_id VARCHAR PRIMARY KEY,
    email VARCHAR,
    membership_upload JSONB,
    predictor_upload JSONB,
    selected_road_tags TEXT[],
    submitted BOOL,
    notified_end BOOL,
    stage INT,
    status VARCHAR,
    version VARCHAR,
    epsg INT,
    config JSONB,
    celery_task_id VARCHAR,
    start_date DATE
);

-- Application logging table
DROP TABLE IF EXISTS logs;

CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    pid INTEGER NOT NULL,
    level VARCHAR(10) NOT NULL,
    module VARCHAR(50) NOT NULL,
    message TEXT NOT NULL
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS logs_timestamp_idx ON logs (timestamp);
CREATE INDEX IF NOT EXISTS logs_pid_idx ON logs (pid);
CREATE INDEX IF NOT EXISTS logs_level_idx ON logs (level);

-- psql -U cosmonaut -p 5432 -h localhost -d cosmonaut_db
-- psql -U USER -p PORT -h HOST -d DATABASE
-- psql -U cosmonaut_stage_adm -p 5432 -h postgres-dev.intranet.ufz.de -d cosmonaut_stage
-- psql -U cosmonaut_prod_adm -p 5432 -h postgres.intranet.ufz.de -d cosmonaut_prod
-- SELECT * FROM jobs;
-- DELETE FROM jobs;
-- SELECT * FROM logs;


-- ============================================================================
-- HOW TO OVERRIDE PRODUCTION DATABASE WITH THIS INIT.SQL
-- ============================================================================
-- WARNING: This will DROP all existing tables and data! Make a backup first!
--
-- 1. Create a backup of the production database:
--    pg_dump -U cosmonaut_stage_adm -h postgres.intranet.ufz.de -d cosmonaut_prod -F c -f backup_$(date +%Y%m%d_%H%M%S).dump
--
-- 2. Execute this init.sql file against the production database:
--    psql -U cosmonaut_prod_adm -p 5432 -h postgres.intranet.ufz.de -d cosmonaut_prod -f docker/init.sql
--
-- 3. Verify the tables were recreated:
--    psql -U cosmonaut_prod_adm -p 5432 -h postgres.intranet.ufz.de -d cosmonaut_prod -c "\dt"
--
-- For staging environment:
--    psql -U cosmonaut_stage_adm -p 5432 -h postgres-dev.intranet.ufz.de -d cosmonaut_stage -f docker/init.sql
--
-- Note: This script uses DROP TABLE IF EXISTS, so it will delete all existing data
-- ============================================================================
