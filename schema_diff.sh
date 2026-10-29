#!/bin/bash

set -euo pipefail

# Compare a live database's tables and columns with docker/init.sql. Read-only on the
# target. The reference schema comes from a throwaway container queried via docker exec,
# so this works with the VPN on (the VPN is what reaches the UFZ databases).
#
# Usage: ./schema_diff.sh <host> <db> <user>      password from ~/.pgpass
# Example: ./schema_diff.sh postgres.intranet.ufz.de somweb_prod somweb_prod_adm
#
# Output is a diff: "<" only in init.sql, ">" only in the live DB. Tables init.sql does
# not own are left out: spatial_ref_sys (PostGIS), health_check (written by the cluster)
# and celery_*/kombu_* (left over from the SQL Celery backend before the move to Redis).

if [ $# -ne 3 ]; then
    echo "Usage: $0 <host> <db> <user>"
    exit 1
fi
HOST=$1
DB=$2
DB_USER=$3

CONTAINER=schema_diff_$$
# Same image as the postgres service in docker-compose.yml.
IMAGE=postgis/postgis:17-3.5

QUERY="SELECT c.table_name || '.' || c.column_name || ' ' || c.data_type
FROM information_schema.columns c
JOIN information_schema.tables t USING (table_schema, table_name)
WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
  AND c.table_name NOT IN ('spatial_ref_sys', 'health_check')
  AND c.table_name NOT LIKE 'celery\_%' AND c.table_name NOT LIKE 'kombu\_%'
ORDER BY 1"

trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1' EXIT

docker run -d --name "$CONTAINER" --network none -e POSTGRES_PASSWORD=x \
    -v "$(dirname "$0")/docker/init.sql:/docker-entrypoint-initdb.d/init.sql:ro" \
    "$IMAGE" >/dev/null
# The entrypoint restarts the server after running init.sql, so wait for the final one.
for _ in $(seq 60); do
    docker logs "$CONTAINER" 2>&1 | grep -q "PostgreSQL init process complete" && break
    if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" != true ]; then
        docker logs "$CONTAINER" 2>&1 | tail -5
        echo "init.sql failed in the reference container" >&2
        exit 1
    fi
    sleep 1
done
until docker exec "$CONTAINER" pg_isready -U postgres -q; do
    sleep 1
done

REFERENCE=$(docker exec "$CONTAINER" psql -U postgres -At -v ON_ERROR_STOP=1 -c "$QUERY")
LIVE=$(psql -h "$HOST" -d "$DB" -U "$DB_USER" -w -At -v ON_ERROR_STOP=1 -c "$QUERY")

if diff <(echo "$REFERENCE") <(echo "$LIVE"); then
    echo "$DB matches docker/init.sql"
else
    exit 1
fi
