#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <mock|prod>"
    exit 1
fi

if [ "$1" == "mock" ]; then
    env_file=".env_test_priv"
elif [ "$1" == "prod" ]; then
    env_file=".env_test_priv_123"
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

if [ "$1" == "prod" ]; then
    docker compose up --no-log-prefix cosmonaut
else
    docker compose up --no-log-prefix --attach cosmonaut 
fi
