#!/usr/bin/env bash
# install.sh — curl bootstrap for My Skill-Agents Library.
# Usage: curl -fsSL <raw-url>/install.sh | sudo bash
#
# Idempotent: re-running pulls the latest code, rewrites the unit, and leaves
# the nginx route and the crontab line alone if they are already there.
set -euo pipefail

RUN_USER="${SUDO_USER:-$(whoami)}"
USER_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
REPO_URL="https://github.com/Epaminondaslage/my-skill-agents-library.git"
TARGET="/opt/skill-agents-library"
MARK_BEGIN="# >>> my-skill-agents-library >>>"
MARK_END="# <<< my-skill-agents-library <<<"

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

# ---------------------------------------------------------------------------
# systemd unit. Group is hardcoded to www-data in the template (nginx must be
# able to reach the socket), so only user and home are substituted here.
# ---------------------------------------------------------------------------
sed \
  -e "s/@RUN_USER@/$RUN_USER/" \
  -e "s#@USER_HOME@#$USER_HOME#" \
  "$TARGET/src/skill-agents-library.service.in" \
  > /etc/systemd/system/skill-agents-library.service
chmod 644 /etc/systemd/system/skill-agents-library.service

systemctl daemon-reload
systemctl enable --now skill-agents-library.service

# ---------------------------------------------------------------------------
# nginx route. Only sites-ENABLED counts, and the location blocks must live
# inside an existing server{} — so they are injected into the enabled vhost
# that serves /var/www/html, between markers uninstall.sh can strip again.
# ---------------------------------------------------------------------------
pick_vhost() {
  local link real tls="" first=""
  for link in /etc/nginx/sites-enabled/*; do
    [[ -e "$link" ]] || continue
    real="$(readlink -f "$link")"
    [[ -f "$real" ]] || continue
    grep -qs 'root[[:space:]]*/var/www/html;' "$real" || continue
    [[ -z "$first" ]] && first="$real"
    if [[ -z "$tls" ]] && grep -qs 'listen[[:space:]]*443' "$real"; then tls="$real"; fi
  done
  echo "${tls:-$first}"                 # prefer the TLS vhost when there is one
}

VHOST="$(pick_vhost)"
[[ -z "$VHOST" ]] && VHOST=/etc/nginx/sites-available/default

if [[ ! -f "$VHOST" ]]; then
  echo "no nginx vhost found — skipping the nginx route" >&2
elif grep -qF "$MARK_BEGIN" "$VHOST"; then
  echo "nginx route already present in $VHOST"
else
  BACKUP="$VHOST.bak-$(date +%Y%m%d-%H%M%S)"
  cp -a "$VHOST" "$BACKUP"
  awk -v b="$MARK_BEGIN" -v e="$MARK_END" '
    !done && /^[[:space:]]*root[[:space:]]+\/var\/www\/html;/ {
      print; print ""
      print "    " b
      print "    location /skill-library/ {"
      print "        alias /var/www/html/my-skill-agents-library/;"
      print "        try_files $uri $uri/ /skill-library/index.html;"
      print "    }"
      print "    # An exact (=) match takes priority over any regex location."
      print "    location = /skill-library/api {"
      print "        proxy_pass http://unix:/run/skill-agents-library/sock:/;"
      print "        proxy_set_header Host $host;"
      print "        proxy_read_timeout 30s;"
      print "    }"
      print "    " e
      done = 1; next
    }
    { print }
  ' "$BACKUP" > "$VHOST"
  echo "nginx route added to $VHOST (backup: $BACKUP)"
fi

if nginx -t; then
  systemctl reload nginx
else
  echo "nginx -t failed — route NOT applied, restore from the .bak file" >&2
fi

# ---------------------------------------------------------------------------
# Regeneration cron for $RUN_USER (guarded so re-installs never duplicate it).
# ---------------------------------------------------------------------------
CRON_LINE="0 6 * * * bash $TARGET/src/regenerate.sh cron"
if crontab -l -u "$RUN_USER" 2>/dev/null | grep -qF "$TARGET/src/regenerate.sh"; then
  echo "cron entry already installed for $RUN_USER"
else
  ( crontab -l -u "$RUN_USER" 2>/dev/null
    echo "# My Skill-Agents Library — daily regeneration"
    echo "$CRON_LINE"
  ) | crontab -u "$RUN_USER" -
  echo "cron entry installed for $RUN_USER (daily at 06:00)"
fi

# The generator runs as $RUN_USER, so the webroot has to be writable by them.
install -d -o "$RUN_USER" -g www-data -m 2775 /var/www/html/my-skill-agents-library

sudo -u "$RUN_USER" env HOME="$USER_HOME" bash "$TARGET/src/regenerate.sh" force || true

echo "done. http://<host>/skill-library/"
