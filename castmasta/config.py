from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration for the CastMasta agent."""

    scan_timeout: float = 5.0
    default_credentials: Optional[dict] = None
    storage_path: Optional[str] = None
    cast_file_server_port: int = 8089


@dataclass
class DeviceConfig:
    """Configuration for a specific device."""

    identifier: str
    name: str
    address: str
    port: int
    protocol: str
    credentials: Optional[dict] = None
