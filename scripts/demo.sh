#!/usr/bin/env bash
# Demo acceptance script (bash twin of demo.ps1). 7 gates, fail-fast.
# Run:  bash scripts/demo.sh [http://localhost:8000]
set -euo pipefail
API="${1:-http://localhost:8000}"
need() { command -v "$1" >/dev/null || { echo "need $1"; exit 1; }; }
need curl; need jq; need python3

echo "[0] health"
curl -sf "$API/health" | jq -e '.ok == true' >/dev/null && echo "  ok: api healthy"

echo "[1] signup + session"
TS=$(date +%s)
TOKA=$(curl -sf -X POST "$API/api/auth/signup" -H 'Content-Type: application/json' \
  -d "{\"email\":\"demo$TS@x.com\",\"password\":\"demopass12\"}" | jq -r .access_token)
SID=$(curl -sf -X POST "$API/api/sessions" -H "Authorization: Bearer $TOKA" \
  -H 'Content-Type: application/json' -d '{}' | jq -r .id)
[ -n "$SID" ] && echo "  ok: session created"

echo "[2] upload 3 types -> ready"
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==" | base64 -d > /tmp/demo_px.png
for f in seed_kb/rag_guide.txt seed_kb/q3_table.csv /tmp/demo_px.png; do
  DID=$(curl -sf -X POST "$API/api/documents/upload" -H "Authorization: Bearer $TOKA" \
    -F "file=@$f" -F "scope=private" | jq -r .doc_id)
  curl -sf -X POST "$API/api/documents/$DID/process" -H "Authorization: Bearer $TOKA" \
    -H 'Content-Type: application/json' -d '{}' >/dev/null
  for _ in $(seq 1 30); do
    ST=$(curl -sf "$API/api/documents/$DID/status" -H "Authorization: Bearer $TOKA" | jq -r .status)
    [ "$ST" = ready ] && break
    [ "$ST" = failed ] && { echo "DEMO FAIL: $f failed"; exit 1; }
    sleep 2
  done
  [ "$ST" = ready ] && echo "  ok: $(basename $f) ready"
done

sdone() { # sid query token [extra-json]
  curl -sf -N -X POST "$API/api/chat" -H "Authorization: Bearer $3" -H 'Content-Type: application/json' \
    -d "{\"session_id\":\"$1\",\"query\":\"$2\",$4}" | grep '"done"' | tail -1 | sed 's/^data: *//' | jq .done
}
echo "[3] cited answer"
D=$(sdone "$SID" "How long are digital goods refundable under Meridian?" "$TOKA" '"x":0')
[ "$(echo "$D" | jq '.citations | length')" -ge 1 ] && echo "  ok: citations >= 1"
echo "$D" | jq -e '.answer | contains("[1]")' >/dev/null && echo "  ok: answer carries [1]"

echo "[4] repeat -> cached"
D2=$(sdone "$SID" "How long are digital goods refundable under Meridian?" "$TOKA" '"x":0')
echo "$D2" | jq -e '.cached == true' >/dev/null && echo "  ok: second ask cached:true"

echo "[5] agent abstains with trace"
D3=$(sdone "$SID" "What is the Mars office address?" "$TOKA" '"mode":"agent"')
echo "$D3" | jq -e '.answer == "I don'"'"'t know based on the knowledge base."' >/dev/null && echo "  ok: agent abstains"
[ "$(echo "$D3" | jq '.trace_steps')" -ge 2 ] && echo "  ok: trace non-empty"

echo "[6] feedback moves helpfulness"
MID=$(curl -sf "$API/api/sessions/$SID/messages?limit=200" -H "Authorization: Bearer $TOKA" \
  | jq -r '[.[] | select(.role=="assistant")][0].id')
curl -sf -X POST "$API/api/feedback" -H "Authorization: Bearer $TOKA" -H 'Content-Type: application/json' \
  -d "{\"message_id\":\"$MID\",\"rating\":-1,\"comment\":\"demo check\"}" >/dev/null
DOWN=$(curl -sf "$API/api/admin/stats" -H "Authorization: Bearer $TOKA" | jq .feedback_down)
[ "$DOWN" -ge 1 ] && echo "  ok: downvote counted"

echo "[7] second user isolated"
TOKB=$(curl -sf -X POST "$API/api/auth/signup" -H 'Content-Type: application/json' \
  -d "{\"email\":\"demo2$TS@x.com\",\"password\":\"demopass12\"}" | jq -r .access_token)
[ "$(curl -sf "$API/api/sessions" -H "Authorization: Bearer $TOKB" | jq 'length')" -eq 0 ] \
  && echo "  ok: user B sees empty list"
if curl -sf -X POST "$API/api/chat" -H "Authorization: Bearer $TOKB" -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SID\",\"query\":\"hi\"}" >/dev/null 2>&1; then
  echo "DEMO FAIL: B reached A session"; exit 1
else echo "  ok: B blocked from A session"; fi

echo; echo "DEMO 7/7 GREEN"
