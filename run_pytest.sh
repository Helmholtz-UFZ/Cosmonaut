#!/bin/bash

if [ -f .env ]; then
    mv .env .env.bak
fi

cp .env_test .env

# Stop and remove any existing postgres container
docker stop postgres_cosmonaut 2>/dev/null || true
docker rm postgres_cosmonaut 2>/dev/null || true
docker compose up postgres -d

echo "Waiting for PostgreSQL to be ready..."
sleep 3

until docker exec postgres_cosmonaut pg_isready -q 2>/dev/null; do
    echo "Still waiting for PostgreSQL..."
    sleep 1
done

echo "PostgreSQL is ready!"
sleep 1

uv run pytest ./test/test_db_manager.py

if [ -f .env.bak ]; then
    mv .env.bak .env
fi

docker compose down
