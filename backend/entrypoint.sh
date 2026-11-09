#!/bin/sh
set -e

if [ "$RUN_MIGRATIONS" = "1" ]; then
    echo "Running alembic migrations..."
    alembic upgrade head
fi

exec "$@"
