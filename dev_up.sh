#!/bin/bash

# Parse command line arguments
DEBUG_MODE=false
MODE=""

while [[ $# -gt 0 ]]; do
    case $1 in
    -d | --debug)
        DEBUG_MODE=true
        shift
        ;;
    mock | prod)
        MODE="$1"
        shift
        ;;
    *)
        echo "Unknown option: $1"
        echo "Usage: $0 [-d|--debug] <mock|prod>"
        echo "  -d, --debug: Enable debug mode (DEBUG=1)"
        echo "  mock: Use mock environment (env_dev_mock)"
        echo "  prod: Use production environment (env_dev_prod_priv)"
        exit 1
        ;;
    esac
done

if [ -z "$MODE" ]; then
    echo "Usage: $0 [-d|--debug] <mock|prod>"
    echo "  -d, --debug: Enable debug mode (DEBUG=1)"
    echo "  mock: Use mock environment (env_dev_mock)"
    echo "  prod: Use production environment (env_dev_prod_priv)"
    exit 1
fi

if [ "$MODE" == "mock" ]; then
    env_file="env_dev_mock"
elif [ "$MODE" == "prod" ]; then
    env_file="env_dev_prod_priv"
else
    echo "Invalid mode. Use 'mock' or 'prod'."
    exit 1
fi

if [ ! -e "$env_file" ]; then
    echo "File $env_file not found."
    exit 1
fi

# Copy env file and optionally override DEBUG variable
cp "$env_file" .env

if [ "$DEBUG_MODE" = true ]; then
    sed -i 's/^DEBUG=.*/DEBUG=1/' .env
fi

# Check if the uv.lock file has changed since the last Docker build
if [ ! -e ".docker_build_hash" ] || [ "$(sha256sum uv.lock)" != "$(cat .docker_build_hash)" ]; then
    # Build the Docker image
    docker compose build cosmonaut

    # Save the hash of the uv.lock file
    sha256sum uv.lock >.docker_build_hash
fi

if [ "$1" == "prod" ]; then
    docker compose up --no-log-prefix cosmonaut
else
    docker compose up --no-log-prefix --attach cosmonaut
fi
