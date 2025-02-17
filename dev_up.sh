#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <mock|prod>"
    exit 1
fi

if [ "$1" == "mock" ]; then
    env_file=".env_test"
elif [ "$1" == "prod" ]; then
    env_file=".env_prod_priv"
else
    echo "Usage: $0 <mock|prod>"
    echo "Invalid mode. Use 'mock' or 'prod'."
    exit 1
fi

if [ ! -e "$env_file" ]; then
    echo "File $env_file not found."
    exit 1
fi

cp "$env_file" .env

# Check if the poetry.lock file has changed since the last Docker build
if [ ! -e ".docker_build_hash" ] || [ "$(sha256sum poetry.lock)" != "$(cat .docker_build_hash)" ]; then
    # Build the Docker image
    docker compose build cosmonaut

    # Save the hash of the poetry.lock file
    sha256sum poetry.lock >.docker_build_hash
fi

if [ "$1" == "prod" ]; then
    docker compose up --no-log-prefix cosmonaut
else
    docker compose up --no-log-prefix --attach cosmonaut
fi
