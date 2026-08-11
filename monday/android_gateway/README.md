# Monday Android Gateway

FastAPI server for Android device communication with the Monday laptop system.

## Features

- JWT-based device registration and authentication
- 6-digit pairing code flow for secure device pairing
- REST API for action submission and audit logs
- WebSocket for real-time events (notifications, progress updates)
- Permission request/response handling

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set these environment variables before running:

```bash
export MONDAY_GATEWAY_SECRET="your_secure_random_secret"
export MONDAY_DASHBOARD_PORT=8765
```

## Running the Server

```bash
python -m monday.android_gateway.server
# or
uvicorn monday.android_gateway.server:app --host 0.0.0.0 --port 8765
```

## API Endpoints

### Device Registration

**POST /register**
```json
{
  "device_name": "My Pixel 8",
  "device_public_key": "abc123...",
  "device_model": "Pixel 8",
  "android_version": "14",
  "app_version": "1.0.0"
}
```

Response:
```json
{
  "device_id": "a1b2c3d4",
  "device_name": "My Pixel 8",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-01-15T10:30:00Z",
  "pairing_code": "X7K9M2"
}
```

### Confirm Pairing

**POST /pair/{pairing_code}**

Called by laptop dashboard after user enters the 6-digit code.

### Submit Action

**POST /actions**
```json
{
  "action_type": "VOICE_INPUT",
  "target": "monday_assistant",
  "parameters": {"text": "Create an expense tracker app"},
  "risk_level": "LOW",
  "task_id": "task_123"
}
```

### Get Audit Log

**GET /audit?limit=50**

Returns recent actions performed by this device.

### WebSocket Events

**WS /ws/events?token={jwt_token}**

Connect to receive real-time events:
- `status_update`: Task status changes
- `progress_update`: Build/test progress
- `permission_request`: Action requires approval
- `notification`: System notifications
- `task_complete`: Task finished

## Security Notes

1. **Change the JWT secret** in production - never use the default
2. **Use HTTPS/WSS** when deploying beyond localhost
3. **Bind to localhost only** (`127.0.0.1`) for local development
4. **Implement rate limiting** for production deployments
5. **Store tokens securely** on the Android device

## Integration with Monday Core

The gateway integrates with the main Monday orchestrator:

```python
from monday.android_gateway.server import device_store, active_connections

# Broadcast event to all connected devices
await active_connections.broadcast({
    "event_type": "task_complete",
    "payload": {"task_id": "xyz", "status": "success"}
})
```
