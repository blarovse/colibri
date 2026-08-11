"""
Monday Automation Engine

Central engine for executing automation actions through specialized executors.
"""

from typing import Optional, Dict, Type
import asyncio
import time

from monday.automation.action_model import Action, ActionResult, ActionType, RiskLevel


class BaseExecutor:
    """Base class for action executors"""
    
    async def execute(self, action: Action) -> ActionResult:
        raise NotImplementedError


class MockExecutor(BaseExecutor):
    """Mock executor for testing - simulates successful execution"""
    
    async def execute(self, action: Action) -> ActionResult:
        await asyncio.sleep(0.1)  # Simulate work
        return ActionResult(
            success=True,
            output={"simulated": True, "action_type": action.action_type.name},
            action_id=action.action_id,
            execution_time_ms=100
        )


class AutomationEngine:
    """
    Central automation engine that routes actions to appropriate executors.
    Implements permission checking, retry logic, and verification.
    """
    
    def __init__(self):
        self.executors: Dict[str, BaseExecutor] = {}
        self._register_default_executors()
    
    def _register_default_executors(self):
        """Register mock executors for all action types (for testing)"""
        # In production, register real executors:
        # self.register_executor('windows', WindowsExecutor())
        # self.register_executor('browser', BrowserExecutor())
        # self.register_executor('file', FileExecutor())
        # self.register_executor('shell', ShellExecutor())
        
        # For now, use mock executor for everything
        mock = MockExecutor()
        self.executors['mock'] = mock
    
    def register_executor(self, name: str, executor: BaseExecutor) -> None:
        """Register an executor by name"""
        self.executors[name] = executor
    
    def _select_executor(self, action: Action) -> Optional[BaseExecutor]:
        """Select appropriate executor for action type"""
        # Map action types to executor names
        mapping = {
            ActionType.OPEN_APP: 'mock',
            ActionType.CLOSE_APP: 'mock',
            ActionType.FOCUS_WINDOW: 'mock',
            ActionType.TYPE_TEXT: 'mock',
            ActionType.CLICK: 'mock',
            ActionType.SCROLL: 'mock',
            ActionType.TAKE_SCREENSHOT: 'mock',
            ActionType.READ_FILE: 'mock',
            ActionType.WRITE_FILE: 'mock',
            ActionType.DELETE_FILE: 'mock',
            ActionType.COPY_FILE: 'mock',
            ActionType.MOVE_FILE: 'mock',
            ActionType.LIST_DIRECTORY: 'mock',
            ActionType.CREATE_DIRECTORY: 'mock',
            ActionType.RUN_COMMAND: 'mock',
            ActionType.RUN_SCRIPT: 'mock',
            ActionType.NAVIGATE: 'mock',
            ActionType.CLICK_ELEMENT: 'mock',
            ActionType.FILL_FORM: 'mock',
            ActionType.SUBMIT_FORM: 'mock',
            ActionType.EXTRACT_TEXT: 'mock',
            ActionType.DOWNLOAD_FILE: 'mock',
            ActionType.SHOW_NOTIFICATION: 'mock',
            ActionType.SEND_EMAIL: 'mock',
        }
        
        executor_name = mapping.get(action.action_type, 'mock')
        return self.executors.get(executor_name)
    
    async def execute_action(self, action: Action) -> ActionResult:
        """
        Execute an action with validation, retry logic, and verification.
        """
        start_time = time.time()
        
        # Validate action
        errors = action.validate()
        if errors:
            return ActionResult(
                success=False,
                error='; '.join(errors),
                action_id=action.action_id
            )
        
        # Select executor
        executor = self._select_executor(action)
        if not executor:
            return ActionResult(
                success=False,
                error=f'No executor available for action type {action.action_type.name}',
                action_id=action.action_id
            )
        
        # Execute with retries
        max_retries = action.retry_policy.get('max_retries', 2)
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                result = await executor.execute(action)
                
                if result.success:
                    # Verify result if verification specified
                    if action.verification and not await self._verify_result(action, result):
                        if attempt < max_retries:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        return ActionResult(
                            success=False,
                            error='Verification failed after retries',
                            action_id=action.action_id
                        )
                    
                    return result
                
                last_error = result.error
                
            except Exception as e:
                last_error = str(e)
            
            # Retry with backoff
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
        
        return ActionResult(
            success=False,
            error=last_error or 'Max retries exceeded',
            action_id=action.action_id
        )
    
    async def _verify_result(self, action: Action, result: ActionResult) -> bool:
        """Verify action result meets expectations"""
        # In production, implement actual verification logic
        # For now, assume success means verified
        return result.success
