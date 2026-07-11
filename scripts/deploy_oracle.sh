#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-$HOME/apex-trader}"
SERVICE_NAME="${SERVICE_NAME:-kyle-api}"
SYSTEM_ENV_FILE="${SYSTEM_ENV_FILE:-/etc/kyle-api.env}"
WEB_ROOT="${WEB_ROOT:-/var/www/kyle}"
START_TRADER="${START_TRADER:-0}"
API_STARTUP_TIMEOUT_SECONDS="${API_STARTUP_TIMEOUT_SECONDS:-60}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ENV_BACKUP="/tmp/kyle-env-${TIMESTAMP}-$$"

log() {
  printf '\n[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

cleanup() {
  rm -f "$ENV_BACKUP"
}
trap cleanup EXIT

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command is missing: $1" >&2
    exit 1
  }
}

append_env_default() {
  local name="$1"
  local value="$2"
  if ! sudo grep -q "^${name}=" "$SYSTEM_ENV_FILE" 2>/dev/null; then
    printf '%s=%s\n' "$name" "$value" | sudo tee -a "$SYSTEM_ENV_FILE" >/dev/null
  fi
}

wait_for_api() {
  local elapsed=0
  while (( elapsed < API_STARTUP_TIMEOUT_SECONDS )); do
    if curl -fsS http://127.0.0.1:8000/ >/dev/null 2>&1; then
      log "API became ready after ${elapsed} seconds"
      return 0
    fi

    if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
      echo "${SERVICE_NAME} stopped while waiting for API readiness." >&2
      sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
      sudo journalctl -u "$SERVICE_NAME" -n 80 --no-pager || true
      return 1
    fi

    sleep 2
    elapsed=$((elapsed + 2))
  done

  echo "API did not become ready within ${API_STARTUP_TIMEOUT_SECONDS} seconds." >&2
  sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
  sudo journalctl -u "$SERVICE_NAME" -n 80 --no-pager || true
  return 1
}

require_command git
require_command curl
require_command python3
require_command npm
require_command openssl

cd "$REPO_DIR"

log "Stopping autonomous paper trading before deployment"
curl -fsS -X POST http://127.0.0.1:8000/api/autonomous-trader/stop >/dev/null 2>&1 || true

log "Backing up runtime state"
if [[ -d data ]]; then
  cp -a data "data-before-deploy-${TIMESTAMP}"
fi

log "Preserving the local secret environment file"
if [[ -f .env ]]; then
  cp .env "$ENV_BACKUP"
  chmod 600 "$ENV_BACKUP"
  git restore .env 2>/dev/null || true
fi

log "Updating repository from origin/main"
git pull --rebase origin main

if [[ -f "$ENV_BACKUP" ]]; then
  cp "$ENV_BACKUP" .env
  chmod 600 .env
fi

log "Configuring protected system environment"
sudo touch "$SYSTEM_ENV_FILE"
sudo chmod 600 "$SYSTEM_ENV_FILE"

if ! sudo grep -q '^KYLE_OPERATOR_TOKEN=' "$SYSTEM_ENV_FILE"; then
  OPERATOR_TOKEN="$(openssl rand -hex 32)"
  printf 'KYLE_OPERATOR_TOKEN=%s\n' "$OPERATOR_TOKEN" | sudo tee -a "$SYSTEM_ENV_FILE" >/dev/null
else
  OPERATOR_TOKEN="$(sudo sed -n 's/^KYLE_OPERATOR_TOKEN=//p' "$SYSTEM_ENV_FILE" | tail -n 1)"
fi

append_env_default KYLE_MAX_QUOTE_AGE_SECONDS 300
append_env_default KYLE_INTELLIGENCE_CACHE_SECONDS 900
append_env_default KYLE_REENTRY_COOLDOWN_MINUTES 60
append_env_default KYLE_RISK_PER_TRADE_PCT 0.005
append_env_default KYLE_REWARD_RISK_RATIO 2.0
append_env_default KYLE_MAX_DAILY_LOSS_PCT 0.02
append_env_default KYLE_MAX_CONSECUTIVE_LOSSES 3
append_env_default KYLE_MAX_OPEN_RISK_PCT 0.02
append_env_default KYLE_MAX_SECTOR_EXPOSURE_PCT 0.30
append_env_default KYLE_MAX_CORRELATED_GROUP_EXPOSURE_PCT 0.30
append_env_default KYLE_BACKTEST_SLIPPAGE_BPS 5
append_env_default KYLE_STRATEGY_VALIDATION_STATUS UNVALIDATED

log "Running Python compilation and intelligence safeguards"
PYTHON_BIN="python3"
if [[ -x .venv/bin/python ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

"$PYTHON_BIN" -m py_compile \
  main.py \
  api/market_data.py \
  api/historical_data.py \
  api/intelligence.py \
  api/portfolio_constraints.py \
  api/advanced_risk.py \
  api/runtime_hardening.py \
  api/risk_gate.py \
  api/decision_engine.py \
  api/security.py \
  api/strategy_validation.py \
  api/system_readiness.py \
  api/backtest.py \
  api/research.py \
  api/research_execution.py \
  api/shadow_mode.py

"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py' -v

log "Building production dashboard"
npm ci --prefix frontend
npm run build --prefix frontend

log "Publishing dashboard"
sudo mkdir -p "$WEB_ROOT"
sudo find "$WEB_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
sudo cp -a frontend/dist/. "$WEB_ROOT/"

log "Restarting services"
sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl reload nginx
wait_for_api

log "Checking API and security status"
curl -fsS http://127.0.0.1:8000/ | python3 -m json.tool
curl -fsS http://127.0.0.1:8000/api/security/status | python3 -m json.tool

log "Running consolidated intelligence readiness audit"
curl -fsS http://127.0.0.1:8000/api/intelligence/readiness | python3 -m json.tool

if [[ "$START_TRADER" == "1" ]]; then
  log "Starting autonomous paper trader"
  curl -fsS -X POST http://127.0.0.1:8000/api/autonomous-trader/start | python3 -m json.tool
else
  log "Autonomous trader remains stopped; set START_TRADER=1 to start after deployment"
fi

printf '\nDeployment completed successfully.\n'
printf 'Dashboard operator token: %s\n' "$OPERATOR_TOKEN"
printf 'Store this token securely. The dashboard will request it on the first control action.\n'
