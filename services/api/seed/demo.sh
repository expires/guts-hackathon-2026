# Demo shell helpers for docs/DEMO.md. Owned by W8.
# Usage (bash or zsh, needs curl and jq):  source services/api/seed/demo.sh
# Signs in as DEMO_DEVICE_ID (default demo-presenter-01), the same id that `make demo-seed` uses.

export BASE=${BASE:-http://localhost:8000}
export DEMO_DEVICE_ID=${DEMO_DEVICE_ID:-demo-presenter-01}
export TOKEN=$(curl -s -X POST $BASE/v1/auth/demo -H 'content-type: application/json' \
  -d "{\"device_id\":\"$DEMO_DEVICE_ID\"}" | jq -r .access_token)
api() { curl -s -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' "$@"; }

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
