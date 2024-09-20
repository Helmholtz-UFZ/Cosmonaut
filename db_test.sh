#!/bin/bash

export DB_HOST_NAME=0.0.0.0

if [ -f .env ]; then
    mv .env .env.bak
fi

cp .env_test_priv .env

docker rm postgres
docker compose up postgres -d

until docker exec postgres pg_isready -q; do
    echo "Waiting for PostgreSQL to start..."
    sleep 1
done

pytest -s

if [ -f .env.bak ]; then
    mv .env.bak .env
fi
docker compose down
