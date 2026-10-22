#!/bin/bash

set -e

# Test containers get their own project and container names. The dev stack
# (docker-compose.yml defaults: postgres_cosmonaut, ...) uses the plain names, and the
# old script ran `docker stop/rm` on exactly those, deleting the dev containers
# (2026-10-22). Everything below, including cleanup, goes through this project only.
export COMPOSE_PROJECT_NAME=cosmonaut_test
export POSTGRES_CONTAINER_NAME=postgres_cosmonaut_test
export OBJECT_STORAGE_CONTAINER_NAME=object_storage_cosmonaut_test
export REDIS_CONTAINER_NAME=redis_cosmonaut_test

trap cleaning_up EXIT

# Cleanup function - restores environment and stops services
cleaning_up() {
    # Restore original .env
    if [ -f .env.bak ]; then
        mv .env.bak .env
    fi

    # Remove only this run's containers: `compose down` acts on the project
    # COMPOSE_PROJECT_NAME (set at the top), never on the dev stack or any other container.
    docker compose down >/dev/null 2>&1 || true
}

# Service health check with retry logic
check_service() {
    local check_command="$1"
    local service_name="$2"
    local max_retries=10
    local retry_count=0

    until eval "$check_command"; do
        if [ $retry_count -ge $max_retries ]; then
            echo "FAIL: ${service_name} did not start after ${max_retries} attempts"
            cleaning_up
            exit 1
        fi
        sleep 1
        retry_count=$((retry_count + 1))
    done
    echo "  ${service_name} ready"
}

# Help message
show_help() {
    echo "Usage: ./run_pytest.sh [OPTIONS] [TEST_PATH]"
    echo ""
    echo "The ONLY way to run tests. Do NOT run pytest directly."
    echo ""
    echo "This script manages the test environment: backs up .env, starts Docker"
    echo "services, runs pytest, then restores .env and stops services on exit."
    echo ""
    echo "Options:"
    echo "  --headed          Run browser tests with visible browser (for debugging)"
    echo "  --local-sr        Use local ../sensor-routing instead of PyPI version"
    echo "  --no-services     Skip Docker service start/stop (services must already be running)."
    echo "                    WARNING: also passes --no-services to pytest, which causes"
    echo "                    dash_app and celery_worker fixtures to SKIP. This means ALL"
    echo "                    e2e tests and most module tests will be SKIPPED. Only useful"
    echo "                    for tests that need no services (test_env, test_html_id_enforcement,"
    echo "                    test_sensor_routing_descriptions)."
    echo "  --no-artifacts    Disable Playwright artifact capture (screenshots, traces)"
    echo "  --keep-artifacts  Keep artifacts from previous runs (default: clear on each run)"
    echo "  -v, --verbose     Show full pytest output (default: minimal, logs go to artifacts)"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Environment:"
    echo "  Test containers: postgres_cosmonaut_test, object_storage_cosmonaut_test,"
    echo "                    redis_cosmonaut_test (compose project cosmonaut_test). The dev stack's"
    echo "                    postgres_cosmonaut etc. are never stopped or removed."
    echo "  COSMO_ECOSYSTEM_PATH  Test against a local cosmo-ecosystem checkout instead of"
    echo "                    the tag pinned in pyproject.toml/uv.lock. When set, the script"
    echo "                    runs 'uv sync --frozen', then 'uv pip install --python .venv"
    echo "                    --editable \$COSMO_ECOSYSTEM_PATH', and runs pytest with"
    echo "                    'uv run --no-sync'."
    echo "                    UV_NO_SYNC=1 is exported too, so the Celery worker subprocess"
    echo "                    (started with 'uv run celery') does not re-sync the overlay away."
    echo "                    Unset: behaviour is unchanged. Nothing in the repo stores the path."
    echo "                    See cosmo-ecosystem docs/conventions/cross_repo_development.md."
    echo ""
    echo "Test Selection:"
    echo "  [TEST_PATH]       Specific test file, directory, or pytest node ID (optional)."
    echo "                    Passed directly to pytest as the last argument."
    echo "                    Examples: test/test_complete_routing_workflow.py"
    echo "                              test/test_complete_routing_workflow.py::test_something"
    echo ""
    echo "Note: This script does NOT support arbitrary pytest flags like -k, -x, etc."
    echo "Only the options listed above are supported."
    echo ""
    echo "Examples:"
    echo "  ./run_pytest.sh                                        # Run all tests"
    echo "  ./run_pytest.sh --headed                               # Visible browser"
    echo "  ./run_pytest.sh test/test_complete_routing_workflow.py  # Specific file"
    echo "  ./run_pytest.sh test/test_complete_routing_workflow.py::test_something"
    echo "  ./run_pytest.sh --keep-artifacts test/test_db_manager.py"
    echo "  ./run_pytest.sh --local-sr test/test_complete_routing_workflow.py"
    echo "  ./run_pytest.sh --no-services test/test_env.py"
    echo "  COSMO_ECOSYSTEM_PATH=~/git/cosmo-ecosystem ./run_pytest.sh  # Local framework"
    echo ""
    echo "Artifacts (on failure): screenshots, traces, HTML in test/artifacts/"
    echo "Full pytest output: test/artifacts/pytest_output.log"
    echo "View traces: npx playwright show-trace test/artifacts/<test-name>/trace.zip"
    exit 0
}

# Parse command line arguments
START_SERVICES=1
HEADED=false
LOCAL_SR=false
ARTIFACTS=true
KEEP_ARTIFACTS=false
VERBOSE=false
TEST_PATH=""

while [[ $# -gt 0 ]]; do
    case $1 in
    --headed)
        HEADED=true
        shift
        ;;
    --local-sr)
        LOCAL_SR=true
        shift
        ;;
    --no-services)
        START_SERVICES=0
        shift
        ;;
    --no-artifacts)
        ARTIFACTS=false
        shift
        ;;
    --keep-artifacts)
        KEEP_ARTIFACTS=true
        shift
        ;;
    -v | --verbose)
        VERBOSE=true
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

# Validate --local-sr
if [ "$LOCAL_SR" = true ]; then
    if [ ! -d "../sensor-routing" ]; then
        echo "Error: ../sensor-routing directory not found."
        echo "Clone sensor-routing as a sibling directory first."
        exit 1
    fi
    SR_PATH="$(cd ../sensor-routing && pwd)"
    export PYTHONPATH="${SR_PATH}:${PYTHONPATH:-}"
    echo "Using local sensor-routing from ${SR_PATH}"
fi

# Overlay a local cosmo-ecosystem checkout (see --help). The variable lives only in
# the caller's shell, so no local path is ever committed.
UV_RUN="uv run"
if [ -n "${COSMO_ECOSYSTEM_PATH:-}" ]; then
    if [ ! -d "$COSMO_ECOSYSTEM_PATH" ]; then
        echo "Error: COSMO_ECOSYSTEM_PATH=${COSMO_ECOSYSTEM_PATH} is not a directory."
        exit 1
    fi
    echo "Overlaying cosmo-ecosystem from ${COSMO_ECOSYSTEM_PATH}"
    uv sync --frozen
    # --python: `uv pip` targets an activated VIRTUAL_ENV before the project .venv,
    # which would put the overlay into the wrong environment.
    uv pip install --python .venv --editable "$COSMO_ECOSYSTEM_PATH"
    UV_RUN="uv run --no-sync"
    # A plain `uv run` re-syncs to uv.lock and silently puts the pinned tag back.
    # conftest starts the Celery worker with `uv run celery`; this keeps it on the
    # overlay without the test code knowing about it.
    export UV_NO_SYNC=1
fi

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
    docker compose down 2>/dev/null || true

    # Start services (quiet output)
    echo "Starting services: postgres, object-storage, redis"
    docker compose up postgres object-storage redis -d --quiet-pull

    # Wait for services with retry logic
    # -h 127.0.0.1 forces the TCP check. Without it pg_isready probes the Unix
    # socket, which already answers during initdb's temporary server phase —
    # that server sets listen_addresses='' and serves no TCP at all. The check
    # then reports "ready" while the endpoint the tests actually use (localhost
    # :POSTGRES_PORT) is still down, and the first query dies with "server closed
    # the connection unexpectedly". Measured window ~1s, wider on a loaded
    # machine. .gitlab-ci.yml already checks over TCP, which is why CI never saw
    # this.
    check_service "docker exec $POSTGRES_CONTAINER_NAME pg_isready -q -h 127.0.0.1 2>/dev/null" "PostgreSQL"
    # The compose healthcheck owns the server-specific probe; this only reads its verdict.
    check_service "docker inspect -f '{{.State.Health.Status}}' $OBJECT_STORAGE_CONTAINER_NAME 2>/dev/null | grep -qx healthy" "Object storage"
    check_service "docker exec $REDIS_CONTAINER_NAME redis-cli ping 2>/dev/null | grep -q PONG" "Redis"
else
    echo "Skipping service management (assuming services already running)"
fi

# Clear previous artifacts unless --keep-artifacts is set
if [ "$KEEP_ARTIFACTS" = false ] && [ -d test/artifacts ]; then
    rm -rf test/artifacts/*
fi
mkdir -p test/artifacts

# Build pytest command dynamically based on flags
PYTEST_CMD="$UV_RUN pytest"

# Add artifact flags (enabled by default)
if [ "$ARTIFACTS" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --screenshot only-on-failure --tracing retain-on-failure --output test/artifacts"
fi

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

# Run pytest — output goes to temp file, moved into artifacts after Playwright is done.
# Playwright cleans --output dir when all tests pass, so writing there during the run
# would lose the log.
TMP_LOG=$(mktemp)
LOG_FILE="test/artifacts/pytest_output.log"

set +e
if [ "$VERBOSE" = true ]; then
    echo "Running: $PYTEST_CMD"
    bash -c "$PYTEST_CMD" 2>&1 | tee "$TMP_LOG"
    PYTEST_EXIT=${PIPESTATUS[0]}
else
    echo "Running tests (logs: $LOG_FILE) ..."
    bash -c "$PYTEST_CMD" > "$TMP_LOG" 2>&1
    PYTEST_EXIT=$?
fi

mkdir -p test/artifacts
mv "$TMP_LOG" "$LOG_FILE"

if [ "$VERBOSE" = false ]; then
    echo ""
    grep -E "^(FAILED|ERROR|=)" "$LOG_FILE" | tail -20 || true
    echo "Full output: $LOG_FILE"
fi
exit $PYTEST_EXIT
