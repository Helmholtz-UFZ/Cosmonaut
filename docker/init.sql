-- init.sql

-- SQL ist nur für verwaltungsstuff

-- Jobs table
DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs (
    job_id VARCHAR PRIMARY KEY,
    start_date DATE,
    end_date DATE,
    data_uploaded BOOL DEFAULT FALSE,
    submitted BOOL,
    email VARCHAR,
    notified_end BOOL,
    stage INT,
    status VARCHAR,
    version DECIMAL
);

-- psql -U cosmonaut -p 5432 -h localhost -d cosmonaut_db
-- psql -U USER -p PORT -h HOST -d DATABASE
-- SELECT * FROM jobs;
-- DELETE FROM jobs;