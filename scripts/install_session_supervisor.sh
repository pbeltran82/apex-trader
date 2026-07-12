#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-$HOME/apex-trader}"
SYSTEM_ENV_FILE="${SYSTEM_ENV_FILE:-/etc/kyle-api.env}"
RUN_USER="${RUN_USER:-$(id -un)}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

sudo tee /etc/systemd/system/kyle-session-supervisor.service >/dev/null <<EOF
[Unit]
Description=Kyle shadow market session supervisor
After=network-online.target kyle-api.service
Wants=network-online.target
Requires=kyle-api.service

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_DIR
EnvironmentFile=$SYSTEM_ENV_FILE
ExecStart=$PYTHON_BIN $REPO_DIR/scripts/market_session_supervisor.py
Restart=no
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/kyle-session-supervisor.timer >/dev/null <<'EOF'
[Unit]
Description=Start Kyle shadow supervisor before US market open

[Timer]
OnCalendar=Mon..Fri *-*-* 06:25:00 America/Los_Angeles
Persistent=true
AccuracySec=1s
Unit=kyle-session-supervisor.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kyle-session-supervisor.timer
sudo systemctl stop kyle-session-supervisor.service >/dev/null 2>&1 || true

printf 'Installed Kyle session timer for 06:25 America/Los_Angeles, Monday-Friday.\n'
systemctl is-enabled kyle-session-supervisor.timer
systemctl is-active kyle-session-supervisor.timer
systemctl list-timers kyle-session-supervisor.timer --no-pager
