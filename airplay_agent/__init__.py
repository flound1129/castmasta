"""AirPlay Agent - LLM agent for controlling AirPlay devices."""

from .agent import AirPlayAgent
from .config import AgentConfig, DeviceConfig

__version__ = "0.1.0"
__all__ = ["AirPlayAgent", "AgentConfig", "DeviceConfig"]
