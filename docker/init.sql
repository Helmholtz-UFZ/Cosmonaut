-- init.sql

-- SQL ist nur für verwaltungsstuff

-- Jobs table
DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs (
    job_id VARCHAR PRIMARY KEY,
    email VARCHAR,
    classification_upload JSONB,
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
-- SELECT * FROM jobs;
-- DELETE FROM jobs;
-- SELECT * FROM logs;
