"""CastMasta - LLM agent for controlling AirPlay and Google Cast devices."""

from .agent import CastAgent
from .config import AgentConfig, DeviceConfig

__version__ = "0.2.0"
__all__ = ["CastAgent", "AgentConfig", "DeviceConfig"]
