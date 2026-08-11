#!/bin/bash
# Monday Android Gateway Smoke Test
set -e

echo "=============================================="
echo "MONDAY ANDROID GATEWAY SMOKE TEST"
echo "=============================================="

# (1) Kill any existing gateway processes and free the port
echo "[0] Cleaning up previous instances..."
pkill -f "monday.android_gateway" 2>/dev/null || true
pkill -f "uvicorn.*android_gateway" 2>/dev/null || true
fuser -k 8765/tcp 2>/dev/null || true
fuser -k 8766/tcp 2>/dev/null || true
sleep 2

# (2) Find free ports automatically using Python
find_free_port() {
    python3 -c "
import socket
def find_port(start):
    for port in range(start, 65535):
        try:
            s = socket.socket()
            s.bind(('127.0.0.1', port))
            s.close()
            return port
        except:
            pass
    return 0
print(find_port($1))
"
}

HTTP_PORT=$(find_free_port ${MONDAY_HTTP_PORT:-8765})
WS_PORT=$(find_free_port ${MONDAY_WS_PORT:-8766})

if [ "$HTTP_PORT" = "0" ] || [ "$WS_PORT" = "0" ]; then
    echo "[X] Could not find free ports"
    exit 1
fi

echo "[*] Using HTTP port: $HTTP_PORT, WebSocket port: $WS_PORT"

cd /workspace/monday/android_gateway

# Start server with configurable ports
export MONDAY_HTTP_PORT=$HTTP_PORT
export MONDAY_WS_PORT=$WS_PORT
uvicorn server:app --host 127.0.0.1 --port $HTTP_PORT > /tmp/gateway_smoke.log 2>&1 &
GATEWAY_PID=$!
echo "[1] Server started (PID: $GATEWAY_PID)"

# (3) Wait for health endpoint with retry loop (up to 15s)
echo "[*] Waiting for server to be healthy..."
MAX_RETRIES=15
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    HEALTH_RESP=$(curl -s http://127.0.0.1:$HTTP_PORT/health 2>/dev/null || echo "")
    if [ -n "$HEALTH_RESP" ] && echo "$HEALTH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='healthy' else 1)" 2>/dev/null; then
        echo "[2] Server healthy"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 1
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "[X] Server not responding after $MAX_RETRIES seconds"
    echo "Server log:"
    cat /tmp/gateway_smoke.log
    kill $GATEWAY_PID 2>/dev/null || true
    exit 1
fi

# Register device
REGISTER_RESP=$(curl -s -X POST http://127.0.0.1:$HTTP_PORT/register \
    -H "Content-Type: application/json" \
    -d '{"device_name":"SmokeTest","device_public_key":"smoke_test","device_model":"Test","android_version":"14"}')
DEVICE_ID=$(echo $REGISTER_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['device_id'])")
PAIRING_CODE=$(echo $REGISTER_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['pairing_code'])")
TOKEN=$(echo $REGISTER_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "[3] Device registered: $DEVICE_ID"

# Pair device
PAIR_RESP=$(curl -s -X POST "http://127.0.0.1:$HTTP_PORT/pair/$PAIRING_CODE" \
    -H "Content-Type: application/json" \
    -d "{\"device_id\":\"$DEVICE_ID\"}")
NEW_TOKEN=$(echo $PAIR_RESP | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
[ -n "$NEW_TOKEN" ] && TOKEN=$NEW_TOKEN
echo "[4] Device paired"

# Submit action
ACTION_RESP=$(curl -s -X POST http://127.0.0.1:$HTTP_PORT/actions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"action_type":"OPEN_APP","target":"Chrome","parameters":{},"risk_level":"LOW"}')
ACTION_ID=$(echo $ACTION_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['action_id'])")
echo "[5] Action submitted: $ACTION_ID"

# Approve action
curl -s -X POST "http://127.0.0.1:$HTTP_PORT/permissions/$ACTION_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"approved":true,"action_id":"'"$ACTION_ID"'"}' > /dev/null
echo "[6] Approval sent"

# Wait for execution
sleep 2

# Get audit log
AUDIT_RESP=$(curl -s http://127.0.0.1:$HTTP_PORT/audit -H "Authorization: Bearer $TOKEN")
echo "[7] Audit entries:"
echo "$AUDIT_RESP" | python3 -c "import sys,json; data=json.load(sys.stdin); entries=data if isinstance(data,list) else data.get('entries',[]); [print(f'       - {e.get(\"action_type\",\"N/A\")}: {e.get(\"status\",\"N/A\")}') for e in entries[-5:]]"

# Cleanup
kill $GATEWAY_PID 2>/dev/null || true
echo "[8] Server stopped"
echo "=============================================="
echo "SMOKE TEST COMPLETED"
echo "=============================================="
