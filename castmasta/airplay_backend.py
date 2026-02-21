"""AirPlay backend using pyatv."""

import asyncio
import logging
from typing import Optional

import pyatv
from pyatv.const import Protocol
from pyatv.storage.memory_storage import MemoryStorage

from .backend import DeviceBackend
from .credentials import CredentialStore

logger = logging.getLogger(__name__)

# Fixed UDP ports for RAOP timing/control so firewall rules stay stable.
RAOP_TIMING_PORT = 50001
RAOP_CONTROL_PORT = 50002


class _PinnedPortStorage(MemoryStorage):
    """MemoryStorage that pins RAOP timing/control to fixed UDP ports."""

    async def get_settings(self, config):
        settings = await super().get_settings(config)
        settings.protocols.raop.timing_port = RAOP_TIMING_PORT
        settings.protocols.raop.control_port = RAOP_CONTROL_PORT
        return settings


_storage = _PinnedPortStorage()


class AirPlayBackend(DeviceBackend):
    """Backend for AirPlay devices (Apple TV, HomePod, AV receivers, etc.)."""

    device_type = "airplay"

    def __init__(self, credentials: Optional[CredentialStore] = None):
        self._atv = None
        self._credentials = credentials

    async def connect(self, identifier: str, address: str, name: str, **kwargs) -> None:
        atvs = await pyatv.scan(
            loop=asyncio.get_event_loop(), timeout=10, hosts=[address],
        )
        target = next((a for a in atvs if a.name == name), None)
        if target is None:
            # Fall back to identifier match
            target = next((a for a in atvs if str(a.identifier) == identifier), None)
        if target is None:
            raise ValueError(f"AirPlay device '{name}' not found at {address}")

        if self._credentials:
            for proto in (Protocol.AirPlay, Protocol.RAOP, Protocol.Companion):
                creds = self._credentials.get(identifier, proto.name)
                if creds:
                    target.set_credentials(proto, creds)
                    logger.debug("Loaded %s credentials for %s", proto.name, name)

        self._atv = await pyatv.connect(
            target, loop=asyncio.get_event_loop(), storage=_storage,
        )
        logger.info("Connected to AirPlay device: %s", name)

    async def disconnect(self) -> None:
        if self._atv:
            self._atv.close()
            self._atv = None

    async def stream_file(self, file_path: str) -> None:
        await self._atv.stream.stream_file(file_path)

    async def play_url(self, url: str, **kwargs) -> None:
        await self._atv.stream.play_url(url, **kwargs)

    async def play(self) -> None:
        await self._atv.remote_control.play()

    async def pause(self) -> None:
        await self._atv.remote_control.pause()

    async def stop(self) -> None:
        await self._atv.remote_control.stop()

    async def seek(self, position: float) -> None:
        await self._atv.remote_control.set_position(position)

    async def set_volume(self, volume: float) -> None:
        await self._atv.audio.set_volume(volume)

    async def get_volume(self) -> float:
        return self._atv.audio.volume

    async def now_playing(self) -> dict:
        playing = await self._atv.metadata.playing()
        return {
            "media_type": playing.media_type.name,
            "device_state": playing.device_state.name,
            "title": playing.title,
            "artist": playing.artist,
            "album": playing.album,
            "position": playing.position,
            "total_time": playing.total_time,
        }

    async def power_on(self) -> None:
        try:
            await self._atv.power.turn_on()
        except Exception as e:
            logger.warning("power_on not available: %s", e)

    async def power_off(self) -> None:
        await self._atv.power.turn_off()

    async def get_power_state(self) -> bool:
        return self._atv.power.power_state

    async def send_key(self, key: str) -> None:
        """Send a remote control key press (AirPlay-specific)."""
        from pyatv.const import Key

        key_map = {
            "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
            "select": Key.select, "menu": Key.menu, "home": Key.home,
            "play": Key.play, "pause": Key.pause, "play_pause": Key.play_pause,
            "next": Key.next, "previous": Key.previous,
        }
        if key not in key_map:
            raise ValueError(f"Unknown key: {key}")
        await self._atv.remote_control.keypress(key_map[key])
