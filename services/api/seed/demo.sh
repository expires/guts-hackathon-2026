# Demo shell helpers for docs/DEMO.md. Owned by W8.
# Usage (bash or zsh, needs curl and jq):  source services/api/seed/demo.sh
# Signs in as DEMO_DEVICE_ID (default demo-presenter-01), the same id that `make demo-seed` uses.

export BASE=${BASE:-http://localhost:8000}
export DEMO_DEVICE_ID=${DEMO_DEVICE_ID:-demo-presenter-01}
# Sign in. Retries a 429 (the rate limit is per IP and shared by every local client).
TOKEN=""
for _i in 1 2 3 4 5 6; do
  TOKEN=$(curl -s -X POST $BASE/v1/auth/demo -H 'content-type: application/json' \
    -d "{\"device_id\":\"$DEMO_DEVICE_ID\"}" | jq -r '.access_token // empty')
  [ -n "$TOKEN" ] && break
  sleep $((_i * 2))
done
unset _i
export TOKEN
if [ -z "$TOKEN" ] || [ "$TOKEN" = null ]; then echo "demo.sh: sign-in failed. Is the stack up (make up)?" >&2; fi
# api ARGS...: curl with the bearer token. Retries a 429 (rate limited) up to 5 times with a growing wait.
# A 429 request was not processed, so a retry is safe for POST too. Other errors are returned as they are.
# A body read from stdin (`-d @-`) is buffered once, so a retry sends the same body.
api() {
  local out code i a
  local args=()
  for a in "$@"; do
    if [ "$a" = "@-" ]; then args+=("$(cat)"); else args+=("$a"); fi
  done
  for i in 1 2 3 4 5 6; do
    out=$(curl -s -w '\n%{http_code}' -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' "${args[@]}")
    code=${out##*$'\n'}
    [ "$code" = 429 ] || break
    echo "rate limited, retry $i in $((i * 2))s" >&2
    sleep $((i * 2))
  done
  printf '%s\n' "${out%$'\n'*}"
}

# new_life PRESET YEAR SEED -> prints the life id
new_life() {
  api -X POST $BASE/v1/lives -d "{\"mode\":\"preset\",\"preset_id\":\"$1\",\"start_year\":$2,\"seed\":$3}" | jq -r .id
}

# play_to LIFE_ID YEAR [FIRST_CHOICE]
# Answers open events with the default choice, ages until YEAR. FIRST_CHOICE overrides the very first
# event's choice; "alt" picks its first non-default choice.
# Prints one line per event: year, title, choice, sources.
play_to() {
  local id=$1 target=$2 first=${3:-} life ev choice
  life=$(api $BASE/v1/lives/$id)
  while :; do
    while [ "$(jq '.pending_events | length' <<<"$life")" -gt 0 ]; do
      ev=$(jq -c '.pending_events[0]' <<<"$life")
      if [ "$first" = alt ]; then choice=$(jq -r '[.choices[] | select(.is_default | not)][0].id' <<<"$ev"); first=""
      elif [ -n "$first" ]; then choice=$first; first=""
      else choice=$(jq -r '([.choices[] | select(.is_default)] + .choices)[0].id' <<<"$ev"); fi
      jq -r --arg c "$choice" '"\(.year)  \(.title)  -> \($c)  [\([.sources[] | "\(.source):\(.series_id)=\(.status)"] | join(", "))]"' <<<"$ev"
      life=$(api -X POST $BASE/v1/lives/$id/choices -d "{\"event_id\":$(jq '.id' <<<"$ev"),\"choice_id\":\"$choice\"}" | jq '.life')
    done
    [ "$(jq '.year' <<<"$life")" -ge "$target" ] && break
    [ "$(jq '.alive' <<<"$life")" = "true" ] || break
    life=$(api -X POST $BASE/v1/lives/$id/age | jq '.life')
  done
}

# path LIFE_ID -> net worth and Index per year from the summary timeline
path() {
  api $BASE/v1/lives/$1/summary | jq -r '.name as $n | .timeline | group_by(.year) | map(last)[] | "\($n)  \(.year)  net worth \(.net_worth)  autopilot \(.autopilot_net_worth)  index \(.index)"'
}
