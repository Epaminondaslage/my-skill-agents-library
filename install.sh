#!/usr/bin/env bash
# install.sh — curl bootstrap for My Skill-Agents Library.
# Usage: curl -fsSL <raw-url>/install.sh | sudo bash
set -euo pipefail

RUN_USER="${SUDO_USER:-$(whoami)}"
RUN_GROUP="$(id -gn "$RUN_USER")"
USER_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
REPO_URL="https://github.com/Epaminondaslage/my-skill-agents-library.git"
TARGET="/opt/skill-agents-library"

if [[ $EUID -ne 0 ]]; then
  echo "run as root (sudo bash install.sh)" >&2
  exit 1
fi

if [[ -d "$TARGET/.git" ]]; then
  git -C "$TARGET" pull --ff-only
else
  rm -rf "$TARGET"
  git clone --depth 1 "$REPO_URL" "$TARGET"
fi

sudo -u "$RUN_USER" mkdir -p "$USER_HOME/.claude/.skill-library"

sed \
  -e "s/@RUN_USER@/$RUN_USER/" \
  -e "s/@RUN_GROUP@/$RUN_GROUP/" \
  -e "s#@USER_HOME@#$USER_HOME#" \
  "$TARGET/src/skill-agents-library.service.in" \
  > /etc/systemd/system/skill-agents-library.service

systemctl daemon-reload
systemctl enable --now skill-agents-library.service

sudo -u "$RUN_USER" env HOME="$USER_HOME" python3 "$TARGET/src/regenerate.sh" force || true

echo "add an nginx location block proxying /skill-library/ to"
echo "  unix:/run/skill-agents-library/sock  (see docs/nginx-snippet.conf)"
echo "add to crontab: 0 6 * * * bash $TARGET/src/regenerate.sh cron"
