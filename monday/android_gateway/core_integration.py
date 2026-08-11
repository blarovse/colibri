"""
Monday Android Gateway Core Integration

Bridges the FastAPI gateway to the Monday Core system:
- AutomationEngine for action execution
- AuditLog for comprehensive logging
- DeviceConnectionManager for WebSocket status streaming
"""

from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
import uuid

from monday.automation.engine import AutomationEngine
from monday.automation.action_model import Action, ActionType, RiskLevel, ActionResult
from monday.core.audit_log import AuditLog


class GatewayCoreBridge:
    """Singleton bridge between Android Gateway and Monday Core"""
    
    _instance: Optional['GatewayCoreBridge'] = None
    
    def __init__(self):
        self.automation_engine = AutomationEngine()
        self.audit_log = AuditLog()
        self._status_callbacks: Dict[str, list] = {}
        
    @classmethod
    def get_instance(cls) -> 'GatewayCoreBridge':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def approve_and_execute(
        self,
        action_id: str,
        action_data: dict,
        device_id: str,
        status_callback=None
    ) -> ActionResult:
        """
        Approve an action and execute it through the AutomationEngine.
        Streams status updates via callback.
        """
        # Convert action data to Action model
        action = self._create_action_from_data(action_id, action_data, device_id)
        
        # Record approval in audit log
        await self.audit_log.record(
            action=action,
            status="approved",
            requested_by=device_id
        )
        
        # Stream status: queued
        await self._stream_status(action_id, "queued", status_callback)
        
        # Execute through automation engine
        await self._stream_status(action_id, "running", status_callback)
        
        try:
            result = await self.automation_engine.execute_action(action)
            
            # Record execution in audit log
            await self.audit_log.record(
                action=action,
                status="executed" if result.success else "failed",
                requested_by=device_id,
                error=result.error if not result.success else None
            )
            
            # Stream final status
            final_status = "done" if result.success else "failed"
            await self._stream_status(action_id, final_status, status_callback, result)
            
            return result
            
        except Exception as e:
            # Record failure
            await self.audit_log.record(
                action=action,
                status="failed",
                requested_by=device_id,
                error=str(e)
            )
            
            await self._stream_status(action_id, "failed", status_callback, {"error": str(e)})
            
            return ActionResult(success=False, error=str(e))
    
    def _create_action_from_data(self, action_id: str, data: dict, device_id: str) -> Action:
        """Convert API action data to Action model"""
        action_type_str = data.get('action_type', 'TAKE_SCREENSHOT')
        
        # Map string to ActionType enum
        try:
            action_type = ActionType[action_type_str]
        except KeyError:
            action_type = ActionType.TAKE_SCREENSHOT
        
        # Map risk level
        risk_level_str = data.get('risk_level', 'LOW')
        try:
            risk_level = RiskLevel[risk_level_str.upper()]
        except KeyError:
            risk_level = RiskLevel.LOW
        
        return Action(
            action_id=action_id,
            action_type=action_type,
            target=data.get('target', ''),
            parameters=data.get('parameters', {}),
            risk_level=risk_level,
            requires_confirmation=data.get('requires_confirmation', False),
            confirmation_prompt=data.get('confirmation_prompt', ''),
            timeout_seconds=data.get('timeout_seconds', 30),
            verification=data.get('verification', ''),
            requested_by=device_id,
            task_id=data.get('task_id', '')
        )
    
    async def _stream_status(
        self,
        action_id: str,
        status: str,
        callback=None,
        payload: Optional[dict] = None
    ):
        """Stream status update via callback"""
        message = {
            "event_type": "action_status",
            "payload": {
                "action_id": action_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                **(payload or {})
            }
        }
        
        if callback:
            await callback(message)
    
    async def record_audit_entry(
        self,
        action: Action,
        status: str,
        requested_by: str,
        error: Optional[str] = None
    ):
        """Record an entry in the audit log"""
        await self.audit_log.record(action=action, status=status, requested_by=requested_by, error=error)


# Convenience function
async def execute_approved_action(
    action_id: str,
    action_data: dict,
    device_id: str,
    status_callback=None
) -> ActionResult:
    """Execute an approved action through the core bridge"""
    bridge = GatewayCoreBridge.get_instance()
    return await bridge.approve_and_execute(action_id, action_data, device_id, status_callback)
