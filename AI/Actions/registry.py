"""
CYNEXIS — Action Registry
Predefined actions with metadata. The ONLY way to control the robot.
"""

import asyncio
from typing import Any, Callable, Coroutine, Optional
from dataclasses import dataclass, field

from core.constants import ActionName, SafetyLevel, SystemMode
from core.logger import get_logger


log = get_logger("actions.registry")

# Type alias
ActionHandler = Callable[..., Coroutine[Any, Any, dict]]


@dataclass
class ActionDefinition:
    """Metadata for a registered action."""
    name: ActionName
    description: str
    handler: Optional[ActionHandler] = None
    safety_level: SafetyLevel = SafetyLevel.LOW
    allowed_modes: list[SystemMode] = field(default_factory=lambda: [
        SystemMode.NORMAL, SystemMode.MANUAL, SystemMode.AI,
    ])
    timeout_ms: int = 5000
    requires_confirmation: bool = False
    parameters: dict = field(default_factory=dict)


class ActionRegistry:
    """
    Central registry of all valid robot actions.
    Actions must be registered here to be executable.
    """

    def __init__(self):
        self._actions: dict[str, ActionDefinition] = {}

    def register(self, definition: ActionDefinition) -> None:
        """Register an action definition."""
        self._actions[definition.name.value] = definition
        log.debug(f"Registered action: {definition.name.value}")

    def get(self, action_name: str) -> Optional[ActionDefinition]:
        """Get an action definition by name."""
        return self._actions.get(action_name)

    def exists(self, action_name: str) -> bool:
        """Check if an action is registered."""
        return action_name in self._actions

    def list_actions(self) -> list[str]:
        """List all registered action names."""
        return list(self._actions.keys())

    async def execute(self, action_name: str, params: dict = None) -> dict:
        """
        Execute a registered action.

        Returns:
            dict with 'success', 'message', and optional 'data'.
        """
        params = params or {}
        definition = self.get(action_name)

        if not definition:
            return {"success": False, "message": f"Action '{action_name}' not found"}

        if not definition.handler:
            return {"success": False, "message": f"Action '{action_name}' has no handler"}

        try:
            log.info(f"Executing action: {action_name}")
            if asyncio.iscoroutinefunction(definition.handler):
                result = await definition.handler(**params)
            else:
                res = definition.handler(**params)
                if asyncio.iscoroutine(res):
                    result = await res
                else:
                    result = res
            return {"success": True, "message": f"Action '{action_name}' completed", "data": result}
        except Exception as e:
            log.error(f"Action '{action_name}' failed: {e}")
            return {"success": False, "message": f"Action '{action_name}' failed: {e}"}



# Singleton
registry = ActionRegistry()
