"""Abstract base class for device protocol backends."""

from abc import ABC, abstractmethod


class DeviceBackend(ABC):
    """Abstract interface for a streaming device protocol.

    Each instance represents one connected device.
    """

    device_type: str  # "airplay" or "googlecast"

    @abstractmethod
    async def connect(self, identifier: str, address: str, name: str, **kwargs) -> None:
        """Connect to the device."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the device."""

    @abstractmethod
    async def stream_file(self, file_path: str) -> None:
        """Stream a local media file to the device."""

    @abstractmethod
    async def play_url(self, url: str, **kwargs) -> None:
        """Play a URL on the device."""

    @abstractmethod
    async def play(self) -> None:
        """Start or resume playback."""

    @abstractmethod
    async def pause(self) -> None:
        """Pause playback."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop playback."""

    @abstractmethod
    async def seek(self, position: float) -> None:
        """Seek to position in seconds."""

    @abstractmethod
    async def set_volume(self, volume: float) -> None:
        """Set volume (0.0 to 1.0)."""

    @abstractmethod
    async def get_volume(self) -> float:
        """Get current volume level (0.0 to 1.0)."""

    @abstractmethod
    async def now_playing(self) -> dict:
        """Get currently playing media information."""

    @abstractmethod
    async def power_on(self) -> None:
        """Turn on the device."""

    @abstractmethod
    async def power_off(self) -> None:
        """Turn off the device."""

    @abstractmethod
    async def get_power_state(self) -> bool:
        """Get power state. True = on, False = off."""
