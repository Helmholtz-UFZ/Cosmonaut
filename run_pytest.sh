#!/bin/bash

set -e

# Cleanup function - restores environment and stops services
cleaning_up() {
    echo "Cleaning up..."

    # Restore original .env
    if [ -f .env.bak ]; then
        mv .env.bak .env
    fi

    # Stop and remove containers
    docker stop postgres_cosmonaut minio_cosmonaut redis_cosmonaut 2>/dev/null || true
    docker rm postgres_cosmonaut minio_cosmonaut redis_cosmonaut 2>/dev/null || true
    docker compose down 2>/dev/null || true

    echo "Cleanup complete"
}

# Service health check with retry logic
check_service() {
    local check_command="$1"
    local service_name="$2"
    local max_retries=10
    local retry_count=0

    echo "Checking ${service_name}..."
    until eval "$check_command"; do
        if [ $retry_count -ge $max_retries ]; then
            echo "${service_name} failed to start after ${max_retries} attempts"
            echo "Cleaning up..."
            cleaning_up
            exit 1
        fi
        echo "Waiting for ${service_name}... (${retry_count}/${max_retries})"
        sleep 1
        retry_count=$((retry_count + 1))
    done
    echo "${service_name} is ready"
}

# Help message
show_help() {
    echo "Usage: ./run_pytest.sh [OPTIONS] [TEST_PATH]"
    echo ""
    echo "Pytest runner with service management and test selection"
    echo ""
    echo "Options:"
    echo "  --headed          Run Playwright tests with visible browser"
    echo "  --no-services     Skip Docker service management (assume already running)"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Test Selection:"
    echo "  [TEST_PATH]       Specific test file or directory to run (optional)"
    echo ""
    echo "Examples:"
    echo "  ./run_pytest.sh                                      # Run all tests headless"
    echo "  ./run_pytest.sh --headed                             # Run all tests with browser visible"
    echo "  ./run_pytest.sh test/test_app.py                     # Run specific test file"
    echo "  ./run_pytest.sh --no-services test/test_env.py       # Run specific test without services"
    echo "  ./run_pytest.sh --headed test/test_complete_routing_workflow.py  # Run specific test with visible browser"
    echo "  ./run_pytest.sh --headed --no-services test/test_env.py          # Combine all flags"
    exit 0
}

# Parse command line arguments
START_SERVICES=1
HEADED=false
TEST_PATH=""

while [[ $# -gt 0 ]]; do
    case $1 in
    --headed)
        HEADED=true
        shift
        ;;
    --no-services)
        START_SERVICES=0
        shift
        ;;
    -h | --help)
        show_help
        ;;
    *)
        TEST_PATH="$1"
        shift
        ;;
    esac
done

# No validation needed - flags can be combined

# Backup existing .env
if [ -f .env ]; then
    mv .env .env.bak
fi

# Use test environment configuration
cp env_test_local .env

# Source for environment variables
source .env

if [ "$START_SERVICES" -eq 1 ]; then
    # Clean up existing containers
    docker compose down 2>/dev/null
    # Start services
    echo "Starting services: postgres, minio, redis"
    docker compose up postgres minio redis -d

    # Wait for services with retry logic
    check_service "docker exec postgres_cosmonaut pg_isready -q 2>/dev/null" "PostgreSQL"
    check_service "docker exec minio_cosmonaut curl -sf http://localhost:9000/minio/health/ready >/dev/null 2>&1" "MinIO"
    check_service "docker exec redis_cosmonaut redis-cli ping 2>/dev/null | grep -q PONG" "Redis"
else
    echo "Skipping service management (assuming services already running)"
fi

# Build pytest command dynamically based on flags
PYTEST_CMD="uv run pytest"

# Add --no-services flag if needed
if [ "$START_SERVICES" -eq 0 ]; then
    PYTEST_CMD="$PYTEST_CMD --no-services"
fi

# Add --headed flag if needed
if [ "$HEADED" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --headed"
fi

# Add test path if specified
if [ -n "$TEST_PATH" ]; then
    PYTEST_CMD="$PYTEST_CMD $TEST_PATH"
fi

# Run pytest with all accumulated flags
echo "Running: $PYTEST_CMD"
$PYTEST_CMD

# Always cleanup, regardless of test success/failure
cleaning_up
