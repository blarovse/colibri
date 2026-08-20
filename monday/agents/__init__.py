# Monday agents package

from ..core.agent_registry import get_registry, AgentType


def register_default_agents() -> None:
    """
    Register the agents that ship with Monday into the global registry.

    Safe to call repeatedly; registration is idempotent.
    """
    from .coding_agent import CodingAgent
    from .prediction_agent import PredictionAgent, build_default_capabilities

    registry = get_registry()
    if AgentType.CODING not in registry._agents:
        registry.register(
            AgentType.CODING,
            CodingAgent,
            capabilities=[],
            priority=10,
            model_requirements=['coding', 'reasoning'],
        )
    if AgentType.PREDICTION not in registry._agents:
        registry.register(
            AgentType.PREDICTION,
            PredictionAgent,
            capabilities=build_default_capabilities(),
            priority=11,  # predictions are Jarvis's sole specialism
            model_requirements=['reasoning', 'numeric'],
        )
