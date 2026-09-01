#!/usr/bin/env bash
# uninstall.sh — stop and remove the systemd unit, socket dir, and deployed
# code. Never touches ~/.claude/.skill-library (user state is kept).
set -euo pipefail

sudo systemctl stop skill-agents-library.service 2>/dev/null || true
sudo systemctl disable skill-agents-library.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/skill-agents-library.service
sudo systemctl daemon-reload
sudo rm -rf /opt/skill-agents-library
sudo rm -rf /var/www/html/my-skill-agents-library
echo "uninstalled. ~/.claude/.skill-library was left untouched."
