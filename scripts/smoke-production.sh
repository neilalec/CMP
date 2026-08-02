#!/usr/bin/env bash
set -euo pipefail

public_url="${1:-https://squadcm.duckdns.org}"
require_ready="${REQUIRE_READY:-0}"
skip_docker="${SKIP_DOCKER:-0}"
base_url="${public_url%/}"
failures=0
warnings=0

add_result() {
  local status="$1"
  local name="$2"
  local details="$3"

  printf '[%s] %s: %s\n' "$status" "$name" "$details"
  case "$status" in
    FAIL) failures=$((failures + 1)) ;;
    WARN) warnings=$((warnings + 1)) ;;
  esac
}

http_probe() {
  local name="$1"
  local url="$2"
  local allow_degraded="${3:-0}"
  local tmp_file
  local status_code

  tmp_file="$(mktemp)"
  status_code="$(curl -ksS --max-time 15 -o "$tmp_file" -w '%{http_code}' "$url" || true)"

  if [[ "$status_code" == "200" ]]; then
    add_result PASS "$name" "HTTP 200"
  elif [[ "$allow_degraded" == "1" && "$status_code" == "503" ]]; then
    add_result WARN "$name" "HTTP 503 degraded"
  elif [[ "$status_code" == "000" ]]; then
    add_result FAIL "$name" "Unable to connect"
  else
    add_result FAIL "$name" "HTTP ${status_code}"
  fi

  rm -f "$tmp_file"
}

docker_probe() {
  if [[ "$skip_docker" == "1" ]]; then
    add_result WARN "Docker Compose" "Skipped by SKIP_DOCKER=1"
    return
  fi

  if ! docker compose ps >/tmp/cmp-compose-ps.txt 2>/tmp/cmp-compose-ps.err; then
    add_result FAIL "Docker Compose" "$(cat /tmp/cmp-compose-ps.err)"
    return
  fi

  for service in backend frontend squadjs caddy; do
    if docker compose ps "$service" --status running | grep -q "$service"; then
      add_result PASS "Container: $service" "running"
    else
      add_result FAIL "Container: $service" "not running"
    fi
  done

  local restarted
  restarted="$(docker inspect --format '{{.Name}}|{{.RestartCount}}' $(docker compose ps -q) 2>/dev/null | awk -F'|' '$2 > 0 {gsub("^/", "", $1); print $1 "=" $2}' | paste -sd ', ' -)"
  if [[ -n "$restarted" ]]; then
    add_result WARN "Container restarts" "$restarted"
  else
    add_result PASS "Container restarts" "No restarts reported"
  fi
}

echo "CMP production smoke test: $base_url"
echo

http_probe "Public frontend" "$base_url/"
http_probe "Public backend live" "$base_url/api/health/live"
if [[ "$require_ready" == "1" ]]; then
  http_probe "Public backend readiness" "$base_url/api/health"
else
  http_probe "Public backend readiness" "$base_url/api/health" 1
fi
http_probe "Local Caddy health" "http://127.0.0.1/healthz"
docker_probe

echo
echo "Manual checks still needed: Steam login, socket/queue live update, admin diagnostics page, and server info from the admin page."

if [[ "$failures" -gt 0 ]]; then
  exit 1
fi

exit 0
