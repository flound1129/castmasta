"""CastMasta - LLM agent for controlling AirPlay and Google Cast devices."""

from .config import AgentConfig, DeviceConfig

try:
    from .agent import CastAgent
except ImportError:
    CastAgent = None  # Available after agent.py is created

__version__ = "0.2.0"
__all__ = ["CastAgent", "AgentConfig", "DeviceConfig"]
