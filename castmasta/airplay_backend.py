"""AirPlay backend using pyatv."""

import ipaddress
import logging
from typing import Optional

import pyatv
from pyatv import conf, connect as pyatv_connect
from pyatv.const import Protocol

from .backend import DeviceBackend
from .credentials import CredentialStore

logger = logging.getLogger(__name__)


class AirPlayBackend(DeviceBackend):
    """Backend for AirPlay devices (Apple TV, HomePod, etc.)."""

    device_type = "airplay"

    def __init__(self, credentials: Optional[CredentialStore] = None):
        self._atv = None
        self._credentials = credentials

    async def connect(self, identifier: str, address: str, name: str, **kwargs) -> None:
        protocol = kwargs.get("protocol", Protocol.AirPlay)
        device_config = conf.AppleTV(
            address=ipaddress.IPv4Address(address),
            name=name,
        )

        if protocol == Protocol.AirPlay:
            service = conf.AirPlayService(identifier, port=7000)
            if self._credentials:
                creds = self._credentials.get(identifier, "AirPlay")
                if creds:
                    service.credentials = creds
        elif protocol == Protocol.Companion:
            service = conf.CompanionService(port=49153)
            if self._credentials:
                creds = self._credentials.get(identifier, "Companion")
                if creds:
                    service.credentials = creds
        else:
            service = conf.AirPlayService(identifier, port=7000)

        device_config.add_service(service)
        self._atv = await pyatv_connect(device_config)

    async def disconnect(self) -> None:
        if self._atv:
            await self._atv.close()
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
        await self._atv.power.turn_on()

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
