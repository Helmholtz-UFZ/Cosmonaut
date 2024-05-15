-- init.sql

-- Health check table
DROP TABLE IF EXISTS health_check;

CREATE TABLE health_check (
    check_time TIMESTAMP PRIMARY KEY,
    status VARCHAR,
    message VARCHAR
);

GRANT INSERT, UPDATE, DELETE, SELECT ON health_check TO postgres;

-- Jobs table
DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    status VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);