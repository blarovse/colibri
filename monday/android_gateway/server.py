"""
Monday Android Gateway Server

FastAPI server providing:
- JWT device registration and authentication
- REST API for actions and audit logs
- WebSocket for real-time events
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import jwt
import uuid
import json
import asyncio
from enum import Enum

# Configuration
JWT_SECRET = "monday_gateway_secret_change_in_production"  # Load from env in production
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_DAYS = 365

app = FastAPI(title="Monday Android Gateway", version="1.0.0")
security = HTTPBearer(auto_error=False)


# ============================================================================
# Data Models
# ============================================================================

class DeviceRegisterRequest(BaseModel):
    device_name: str = Field(..., description="Human-readable device name")
    device_public_key: str = Field(..., description="Device public key for identification")
    device_model: Optional[str] = None
    android_version: Optional[str] = None
    app_version: Optional[str] = None


class DeviceRegisterResponse(BaseModel):
    device_id: str
    device_name: str
    token: str
    expires_at: datetime
    pairing_code: str  # 6-digit code for user verification


class ActionRequest(BaseModel):
    action_type: str
    target: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "LOW"
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    task_id: Optional[str] = None


class ActionResponse(BaseModel):
    action_id: str
    status: str  # pending, approved, denied, executed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PermissionResponse(BaseModel):
    action_id: str
    approved: bool
    reason: Optional[str] = None


class EventType(str, Enum):
    STATUS_UPDATE = "status_update"
    PROGRESS_UPDATE = "progress_update"
    PERMISSION_REQUEST = "permission_request"
    NOTIFICATION = "notification"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"


class EventMessage(BaseModel):
    event_type: EventType
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuditLogEntry(BaseModel):
    log_id: str
    timestamp: datetime
    device_id: str
    action_type: str
    target: str
    status: str
    risk_level: str
    task_id: Optional[str] = None


# ============================================================================
# In-Memory Storage (Replace with database in production)
# ============================================================================

class DeviceStore:
    def __init__(self):
        self.devices: Dict[str, dict] = {}
        self.pending_pairings: Dict[str, dict] = {}  # pairing_code -> device info

    def register_device(self, device_info: dict) -> tuple[str, str, str]:
        """Register device and return (device_id, token, pairing_code)"""
        device_id = hashlib.sha256(device_info['device_public_key'].encode()).hexdigest()[:16]
        
        # Generate JWT token
        token = jwt.encode(
            {
                'device_id': device_id,
                'device_name': device_info['device_name'],
                'exp': datetime.utcnow() + timedelta(days=TOKEN_EXPIRY_DAYS),
                'iat': datetime.utcnow()
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM
        )
        
        # Generate 6-digit pairing code
        pairing_code = str(uuid.uuid4())[:6].upper()
        
        # Store pending pairing (expires in 5 minutes)
        self.pending_pairings[pairing_code] = {
            'device_id': device_id,
            'device_info': device_info,
            'expires_at': datetime.utcnow() + timedelta(minutes=5)
        }
        
        return device_id, token, pairing_code

    def confirm_pairing(self, pairing_code: str) -> Optional[dict]:
        """Confirm device pairing with code"""
        if pairing_code not in self.pending_pairings:
            return None
        
        pairing = self.pending_pairings[pairing_code]
        if datetime.utcnow() > pairing['expires_at']:
            del self.pending_pairings[pairing_code]
            return None
        
        # Move to confirmed devices
        device_id = pairing['device_id']
        self.devices[device_id] = {
            **pairing['device_info'],
            'confirmed_at': datetime.utcnow(),
            'status': 'active'
        }
        
        del self.pending_pairings[pairing_code]
        return self.devices[device_id]

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            device_id = payload.get('device_id')
            
            if device_id not in self.devices:
                return None
            
            return payload
        except jwt.InvalidTokenError:
            return None

    def get_device(self, device_id: str) -> Optional[dict]:
        return self.devices.get(device_id)


class ActiveConnections:
    """Manage active WebSocket connections per device"""
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        if device_id not in self.connections:
            self.connections[device_id] = []
        self.connections[device_id].append(websocket)

    def disconnect(self, device_id: str, websocket: WebSocket):
        if device_id in self.connections:
            self.connections[device_id].remove(websocket)
            if not self.connections[device_id]:
                del self.connections[device_id]

    async def send_to_device(self, device_id: str, message: dict):
        """Send message to all websockets for a device"""
        if device_id in self.connections:
            message_json = json.dumps(message)
            disconnected = []
            for ws in self.connections[device_id]:
                try:
                    await ws.send_text(message_json)
                except:
                    disconnected.append(ws)
            # Clean up disconnected
            for ws in disconnected:
                self.connections[device_id].remove(ws)

    async def broadcast(self, message: dict):
        """Broadcast to all connected devices"""
        message_json = json.dumps(message)
        for device_id, wss in list(self.connections.items()):
            for ws in wss:
                try:
                    await ws.send_text(message_json)
                except:
                    pass  # Will be cleaned up on next operation


# Global stores
device_store = DeviceStore()
active_connections = ActiveConnections()
action_queue: Dict[str, ActionRequest] = {}
audit_logs: List[AuditLogEntry] = []


# ============================================================================
# Dependencies
# ============================================================================

async def get_current_device(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Authenticate request and return device payload"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials"
        )
    
    payload = device_store.verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return payload


# ============================================================================
# Routes
# ============================================================================

@app.post("/register", response_model=DeviceRegisterResponse)
async def register_device(request: DeviceRegisterRequest):
    """
    Register a new Android device.
    Returns device_id, JWT token, and 6-digit pairing code.
    User must enter pairing code in laptop dashboard to complete pairing.
    """
    device_info = request.model_dump()
    device_id, token, pairing_code = device_store.register_device(device_info)
    
    return DeviceRegisterResponse(
        device_id=device_id,
        device_name=request.device_name,
        token=token,
        expires_at=datetime.utcnow() + timedelta(days=TOKEN_EXPIRY_DAYS),
        pairing_code=pairing_code
    )


@app.post("/pair/{pairing_code}")
async def confirm_pairing(pairing_code: str):
    """
    Confirm device pairing with 6-digit code.
    Called by laptop dashboard after user enters code.
    """
    device_info = device_store.confirm_pairing(pairing_code.upper())
    if not device_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired pairing code"
        )
    
    return {
        "status": "paired",
        "device_id": device_info['device_id'],
        "device_name": device_info['device_name']
    }


@app.post("/actions", response_model=ActionResponse)
async def submit_action(
    request: ActionRequest,
    device: dict = Depends(get_current_device)
):
    """
    Submit an action from the Android device to be executed on the laptop.
    """
    action_id = str(uuid.uuid4())
    
    # Store action
    action_queue[action_id] = request
    
    # Log audit entry
    audit_logs.append(AuditLogEntry(
        log_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        device_id=device['device_id'],
        action_type=request.action_type,
        target=request.target,
        status="pending",
        risk_level=request.risk_level,
        task_id=request.task_id
    ))
    
    # Notify laptop via WebSocket
    await active_connections.broadcast({
        "event_type": "action_submitted",
        "payload": {
            "action_id": action_id,
            "device_id": device['device_id'],
            "action": request.model_dump()
        }
    })
    
    return ActionResponse(
        action_id=action_id,
        status="pending"
    )


@app.get("/actions/{action_id}", response_model=ActionResponse)
async def get_action_status(
    action_id: str,
    device: dict = Depends(get_current_device)
):
    """Get status of a submitted action"""
    # In production, this would query a database
    # For now, return pending status
    return ActionResponse(
        action_id=action_id,
        status="pending"
    )


@app.post("/permissions/{action_id}")
async def respond_to_permission(
    action_id: str,
    response: PermissionResponse,
    device: dict = Depends(get_current_device)
):
    """
    Respond to a permission request from laptop.
    User approves or denies a gated action.
    """
    # Broadcast response to laptop
    await active_connections.broadcast({
        "event_type": "permission_response",
        "payload": {
            "action_id": action_id,
            "approved": response.approved,
            "reason": response.reason,
            "device_id": device['device_id']
        }
    })
    
    # Update audit log
    for log in audit_logs:
        if log.log_id == action_id:
            log.status = "approved" if response.approved else "denied"
            break
    
    return {"status": "recorded"}


@app.get("/audit", response_model=List[AuditLogEntry])
async def get_audit_log(
    limit: int = 50,
    device: dict = Depends(get_current_device)
):
    """Get recent audit log entries for this device"""
    device_logs = [log for log in audit_logs if log.device_id == device['device_id']]
    return device_logs[-limit:]


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for real-time events.
    Connects Android device to receive notifications, progress updates, etc.
    """
    # Authenticate via query param token
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    
    payload = device_store.verify_token(token)
    if not payload:
        await websocket.close(code=4003, reason="Invalid token")
        return
    
    device_id = payload['device_id']
    
    await active_connections.connect(device_id, websocket)
    
    try:
        while True:
            # Keep connection alive, receive messages from device
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle device->laptop messages
            if message.get('type') == 'heartbeat':
                await websocket.send_json({"type": "heartbeat_ack"})
            elif message.get('type') == 'voice_input':
                # Forward voice input to laptop
                await active_connections.broadcast({
                    "event_type": "voice_input",
                    "payload": {
                        "device_id": device_id,
                        "text": message.get('text')
                    }
                })
    except WebSocketDisconnect:
        active_connections.disconnect(device_id, websocket)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "connected_devices": len(active_connections.connections),
        "registered_devices": len(device_store.devices)
    }


# ============================================================================
# Background Tasks
# ============================================================================

async def cleanup_expired_pairings():
    """Periodically clean up expired pending pairings"""
    while True:
        await asyncio.sleep(60)  # Check every minute
        now = datetime.utcnow()
        expired = [
            code for code, info in device_store.pending_pairings.items()
            if now > info['expires_at']
        ]
        for code in expired:
            del device_store.pending_pairings[code]


# Start background tasks
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_expired_pairings())
    print("Monday Android Gateway started")


if __name__ == "__main__":
    import uvicorn
    import hashlib
    uvicorn.run(app, host="0.0.0.0", port=8765)
