"""
Monday Core Audit Log

Records all automation actions for security and traceability.
"""

from typing import Optional, List, Dict
from datetime import datetime
import uuid
from dataclasses import dataclass, field

from monday.automation.action_model import Action


@dataclass
class AuditLogEntry:
    """Single audit log entry"""
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    action_type: str = ''
    target: str = ''
    parameters: dict = field(default_factory=dict)
    risk_level: str = ''
    requested_by: str = ''
    task_id: Optional[str] = None
    status: str = ''  # pending, approved, denied, executed, failed
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class AuditLog:
    """
    In-memory audit log for recording automation actions.
    In production, replace with database-backed implementation.
    """
    
    def __init__(self):
        self._entries: List[AuditLogEntry] = []
    
    async def record(
        self,
        action: Action,
        status: str,
        requested_by: str,
        error: Optional[str] = None,
        execution_time_ms: Optional[float] = None
    ) -> AuditLogEntry:
        """Record an audit log entry"""
        entry = AuditLogEntry(
            action_type=action.action_type.name,
            target=action.target,
            parameters=action.parameters,
            risk_level=action.risk_level.value,
            requested_by=requested_by,
            task_id=action.task_id or None,
            status=status,
            error=error,
            execution_time_ms=execution_time_ms
        )
        
        self._entries.append(entry)
        return entry
    
    def get_entries(
        self,
        limit: int = 100,
        requested_by: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[AuditLogEntry]:
        """Get audit log entries with optional filtering"""
        entries = self._entries
        
        if requested_by:
            entries = [e for e in entries if e.requested_by == requested_by]
        
        if status:
            entries = [e for e in entries if e.status == status]
        
        # Return most recent first, limited
        return list(reversed(entries[-limit:]))
    
    def clear(self):
        """Clear all entries (for testing)"""
        self._entries.clear()
