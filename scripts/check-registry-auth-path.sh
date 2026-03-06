#!/usr/bin/env bash
set -euo pipefail

REGISTRY_URL="${REGISTRY_URL:-https://registry.mcp.joshsr.ai}"
AUTH_PATH="${AUTH_PATH:-/api/auth/me}"
EXPECTED_CODE="${EXPECTED_CODE:-401}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-15}"

url="${REGISTRY_URL%/}${AUTH_PATH}"
response_body="$(mktemp)"
trap 'rm -f "$response_body"' EXIT

if http_code="$(curl -skS --max-time "$TIMEOUT_SECONDS" -o "$response_body" -w '%{http_code}' "$url")"; then
    :
else
    curl_exit_code="$?"
    echo "FAIL: unable to reach $url (curl exit $curl_exit_code)"
    exit "$curl_exit_code"
fi

if [ "$http_code" != "$EXPECTED_CODE" ]; then
    echo "FAIL: $url returned HTTP $http_code (expected $EXPECTED_CODE)"
    echo "Body: $(head -c 240 "$response_body" | tr '\n' ' ')"
    exit 1
fi

echo "OK: $url returned HTTP $http_code (expected)"
