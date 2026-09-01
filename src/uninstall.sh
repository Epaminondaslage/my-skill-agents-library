#!/usr/bin/env bash
# uninstall.sh — stop and remove the systemd unit, the nginx route, the cron
# entry and the deployed code. Never touches ~/.claude/.skill-library (user
# state is kept).
set -euo pipefail

RUN_USER="${SUDO_USER:-$(whoami)}"
MARK_BEGIN="# >>> my-skill-agents-library >>>"
MARK_END="# <<< my-skill-agents-library <<<"

sudo systemctl stop skill-agents-library.service 2>/dev/null || true
sudo systemctl disable skill-agents-library.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/skill-agents-library.service
sudo systemctl daemon-reload

# nginx: strip the marked block from whichever enabled vhost carries it.
for link in /etc/nginx/sites-enabled/*; do
  [[ -e "$link" ]] || continue
  real="$(readlink -f "$link")"
  [[ -f "$real" ]] || continue
  grep -qF "$MARK_BEGIN" "$real" || continue
  backup="$real.bak-$(date +%Y%m%d-%H%M%S)"
  sudo cp -a "$real" "$backup"
  sudo awk -v b="$MARK_BEGIN" -v e="$MARK_END" '
    index($0, b) { skip = 1; next }
    index($0, e) { skip = 0; next }
    !skip { print }
  ' "$backup" | sudo tee "$real" >/dev/null
  echo "nginx route removed from $real (backup: $backup)"
done
if sudo nginx -t 2>/dev/null; then sudo systemctl reload nginx || true; fi

# cron: drop our regeneration line(s) for the invoking user.
if crontab -l -u "$RUN_USER" 2>/dev/null | grep -qiE 'skill[- ]agents[- ]library'; then
  crontab -l -u "$RUN_USER" 2>/dev/null \
    | grep -viE 'skill[- ]agents[- ]library' \
    | crontab -u "$RUN_USER" -
  echo "cron entry removed for $RUN_USER"
fi

sudo rm -rf /opt/skill-agents-library
sudo rm -rf /var/www/html/my-skill-agents-library
echo "uninstalled. ~/.claude/.skill-library was left untouched."
