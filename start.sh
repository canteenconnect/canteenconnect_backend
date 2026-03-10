#!/usr/bin/env bash
set -euo pipefail

export FLASK_APP=run.py

flask db upgrade
flask seed-roles

if [[ -n "${SUPER_ADMIN_EMAIL:-}" && -n "${SUPER_ADMIN_PASSWORD:-}" ]]; then
  flask create-superadmin --email "$SUPER_ADMIN_EMAIL" --password "$SUPER_ADMIN_PASSWORD"
fi

exec gunicorn run:app --bind "0.0.0.0:${PORT:-5000}" --workers 2 --threads 4
