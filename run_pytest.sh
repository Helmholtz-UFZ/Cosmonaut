#!/bin/bash

# Parse command line arguments
HEADED=false
while [[ $# -gt 0 ]]; do
    case $1 in
    --headed)
        HEADED=true
        shift
        ;;
    *)
        echo "Unknown option: $1"
        echo "Usage: $0 [--headed]"
        echo "  --headed: Run browser tests with visible browser window"
        exit 1
        ;;
    esac
done

if [ -f .env ]; then
    mv .env .env.bak
fi

cp env_test_local .env

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

# Run pytest with or without headed mode
if [ "$HEADED" = true ]; then
    echo "Running tests in HEADED mode (browser window visible)..."
    uv run pytest --headed
else
    echo "Running tests in HEADLESS mode (no browser window)..."
    uv run pytest
fi

# Stop docker services before restoring .env
docker compose down

# Restore original .env after docker compose is done
if [ -f .env.bak ]; then
    mv .env.bak .env
fi
