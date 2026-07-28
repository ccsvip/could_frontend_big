#!/usr/bin/env bash
# Verify that a protected PostgreSQL custom-format baseline can migrate to this checkout.
# Requires: Docker Compose db service running and BASELINE_DUMP pointing to a pg_dump -Fc archive.
set -Eeuo pipefail

: "${BASELINE_DUMP:?Set BASELINE_DUMP to a PostgreSQL custom-format dump.}"

if [[ ! -f "$BASELINE_DUMP" ]]; then
  printf 'Baseline dump does not exist: %s\n' "$BASELINE_DUMP" >&2
  exit 2
fi

verify_db="restore_verify_$(date +%s)_$$"
container_dump="/tmp/${verify_db}.dump"

cleanup() {
  local status=$?

  trap - EXIT
  if ! docker compose exec -T \
    -e VERIFY_DB="$verify_db" \
    -e VERIFY_DUMP="$container_dump" \
    db sh -ec '
      if [ "$VERIFY_DB" = "${POSTGRES_DB:?}" ]; then
        echo "Refusing to clean the primary database" >&2
        exit 1
      fi
      rm -f "$VERIFY_DUMP"
      dropdb --force --if-exists -U "$POSTGRES_USER" "$VERIFY_DB"
    ' >/dev/null; then
    printf 'Failed to clean temporary database or copied archive.\n' >&2
    if (( status == 0 )); then
      exit 1
    fi
  fi

  exit "$status"
}
trap cleanup EXIT

if ! docker compose exec -T db sh -ec 'if [ "${POSTGRES_DB:?}" = postgres ]; then readiness_db=template1; else readiness_db=postgres; fi; pg_isready -U "$POSTGRES_USER" -d "$readiness_db" >/dev/null'; then
  printf 'Database service is not ready. Start only it first: docker compose up -d db\n' >&2
  exit 2
fi

container_id="$(docker compose ps -q db)"
if [[ -z "$container_id" ]]; then
  printf 'Database container was not found. Start it first: docker compose up -d db\n' >&2
  exit 2
fi

docker cp "$BASELINE_DUMP" "${container_id}:${container_dump}"

docker compose exec -T \
  -e VERIFY_DB="$verify_db" \
  -e VERIFY_DUMP="$container_dump" \
  db sh -ec '
    if [ "$VERIFY_DB" = "${POSTGRES_DB:?}" ]; then
      echo "Refusing to use the primary database for verification" >&2
      exit 1
    fi
    pg_restore -l "$VERIFY_DUMP" >/dev/null
    createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" -E UTF8 "$VERIFY_DB"
    pg_restore --exit-on-error --no-owner --no-privileges \
      -U "$POSTGRES_USER" -d "$VERIFY_DB" "$VERIFY_DUMP"
  '

docker compose run --rm --no-deps \
  -e VERIFY_DB="$verify_db" \
  backend sh -ec '
    export DATABASE_URL="$(python - <<'"'"'PY'"'"'
import os
from urllib.parse import urlsplit, urlunsplit

url = urlsplit(os.environ["DATABASE_URL"])
database = os.environ["VERIFY_DB"]
if not url.scheme or not url.netloc or url.path in ("", "/"):
    raise SystemExit("DATABASE_URL must include a database name")
print(urlunsplit((url.scheme, url.netloc, f"/{database}", url.query, url.fragment)))
PY
)"
    python manage.py migrate --noinput
    python manage.py migrate --check
    python manage.py makemigrations --check --dry-run
  '

printf 'Baseline upgrade verification passed for temporary database %s.\n' "$verify_db"
