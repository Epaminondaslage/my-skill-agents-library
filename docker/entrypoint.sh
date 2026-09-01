#!/usr/bin/env bash
# entrypoint.sh — container init: prep state dirs, start the backend as the
# unprivileged "app" user, regenerate the static site once, then run a plain
# loop in place of the host's cron (see src/regenerate.sh) before handing off
# to nginx in the foreground.
set -euo pipefail

STATE_DIR="$HOME/.claude/.skill-library"
SOCK_DIR="/run/skill-agents-library"

mkdir -p "$STATE_DIR"
chown -R app:www-data "$STATE_DIR"

mkdir -p "$SOCK_DIR"
chown app:www-data "$SOCK_DIR"
chmod 0770 "$SOCK_DIR"

mkdir -p /var/www/html/my-skill-agents-library
chown app:www-data /var/www/html/my-skill-agents-library
chmod 2775 /var/www/html/my-skill-agents-library

export SKILL_LIBRARY_SOCKET="$SOCK_DIR/sock"
export PYTHONUNBUFFERED=1

su -s /bin/bash app -c "SKILL_LIBRARY_SOCKET=$SKILL_LIBRARY_SOCKET HOME=$HOME PYTHONUNBUFFERED=1 python3 /app/src/serve.py" &

# First render so the site isn't empty while the socket comes up.
su -s /bin/bash app -c "HOME=$HOME bash /app/src/regenerate.sh force" || true

# Daily-equivalent regen loop (cron replacement inside the container).
(
  while true; do
    sleep 3600
    su -s /bin/bash app -c "HOME=$HOME bash /app/src/regenerate.sh cron" || true
  done
) &

exec nginx -g "daemon off;"
