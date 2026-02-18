import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration for the AirPlay agent."""

    loop: asyncio.AbstractEventLoop = field(default_factory=asyncio.get_event_loop)
    scan_timeout: float = 5.0
    default_credentials: Optional[dict] = None
    storage_path: Optional[str] = None


@dataclass
class DeviceConfig:
    """Configuration for a specific device."""

    identifier: str
    name: str
    address: str
    port: int
    protocol: str
    credentials: Optional[dict] = None
