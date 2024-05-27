-- init.sql

-- Health check table
DROP TABLE IF EXISTS health_check;

CREATE TABLE health_check (
    check_time TIMESTAMP PRIMARY KEY,
    status VARCHAR,
    message VARCHAR
);

-- Jobs table
DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs (
    job_id VARCHAR PRIMARY KEY,
    start_date DATE,
    input_data JSONB,
    files BYTEA[],
    file_names VARCHAR[],
    submitted BOOL,
    cluster_job_id VARCHAR,
    email VARCHAR,
    notified_end BOOL,
    logs VARCHAR,
    status VARCHAR,
    version DECIMAL
);
