import asyncio
import ipaddress
import json
import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import pyatv
from pyatv import conf, connect
from pyatv.const import Protocol
from pyatv.interface import AppleTV as AppleTVInterface

from .config import AgentConfig
from .tools import get_tool_definitions

logger = logging.getLogger(__name__)

ALLOWED_MEDIA_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".ogg", ".mp4", ".m4a", ".aac", ".m4v", ".mov",
}

ALLOWED_URL_SCHEMES = {"http", "https"}

MAX_SCAN_TIMEOUT = 30


class CredentialStore:
    """Store and retrieve device credentials."""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".airplay-agent" / "credentials.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.storage_path.parent, 0o700)
        self._credentials: dict = self._load()

    def _load(self) -> dict:
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self):
        dir_ = self.storage_path.parent
        fd = None
        tmp_path = None
        try:
            fd = tempfile.mkstemp(dir=dir_, suffix=".tmp")
            tmp_path = fd[1]
            with os.fdopen(fd[0], "w") as f:
                json.dump(self._credentials, f, indent=2)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.storage_path)
        except OSError:
            logger.exception("Failed to save credentials")
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get(self, identifier: str, protocol: str) -> Optional[str]:
        """Get credentials for a device and protocol."""
        key = f"{identifier}:{protocol}"
        return self._credentials.get(key)

    def set(self, identifier: str, protocol: str, credentials: str):
        """Save credentials for a device and protocol."""
        key = f"{identifier}:{protocol}"
        self._credentials[key] = credentials
        self._save()

    def delete(self, identifier: str, protocol: Optional[str] = None):
        """Delete credentials for a device."""
        if protocol:
            key = f"{identifier}:{protocol}"
            self._credentials.pop(key, None)
        else:
            keys_to_delete = [
                k for k in self._credentials if k.startswith(f"{identifier}:")
            ]
            for key in keys_to_delete:
                del self._credentials[key]
        self._save()


class AirPlayAgent:
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.devices: dict[str, AppleTVInterface] = {}
        self._scan_task: Optional[asyncio.Task] = None
        self.credentials = CredentialStore(self.config.storage_path)
        self._pairing_handlers: dict[str, object] = {}

    async def scan(self, timeout: int = 5) -> list[dict]:
        """Scan for AirPlay devices on the network."""
        timeout = max(1, min(timeout, MAX_SCAN_TIMEOUT))
        atvs = await pyatv.scan(timeout=timeout)
        device_list = []
        for atv in atvs:
            services = atv.services if hasattr(atv, "services") else []
            device_list.append(
                {
                    "name": atv.name,
                    "address": str(atv.address),
                    "identifier": atv.identifier,
                    "protocols": [s.protocol.name for s in services],
                }
            )
        return device_list

    async def pair(
        self,
        identifier: str,
        address: str,
        name: str,
        protocol: Protocol = Protocol.AirPlay,
    ) -> dict:
        """Pair with a device using PIN code.

        Returns a dict with pairing status and instructions.
        The handler is stored internally for use by pair_with_pin.
        """
        device_config = conf.AppleTV(
            address=ipaddress.IPv4Address(address),
            name=name,
        )

        if protocol == Protocol.AirPlay:
            service = conf.AirPlayService(identifier, port=7000)
        elif protocol == Protocol.Companion:
            service = conf.CompanionService(port=49153)
        else:
            raise ValueError(f"Unsupported protocol for pairing: {protocol}")

        device_config.add_service(service)
        handler = await pyatv.pair(device_config, protocol)

        await handler.begin()

        handler_key = f"{identifier}:{protocol.name}"
        self._pairing_handlers[handler_key] = handler

        if not handler.device_provides_pin:
            return {
                "status": "pin_required",
                "message": "Enter PIN on the device itself",
            }

        return {
            "status": "ready",
            "message": "PIN required - use pair_with_pin method",
        }

    async def pair_with_pin(
        self,
        identifier: str,
        address: str,
        name: str,
        pin: str,
        protocol: Protocol = Protocol.AirPlay,
    ) -> bool:
        """Complete pairing with a PIN code."""
        handler_key = f"{identifier}:{protocol.name}"
        handler = self._pairing_handlers.get(handler_key)

        if handler is None:
            raise ValueError(
                f"No active pairing session for {identifier}. Call pair() first."
            )

        try:
            handler.pin(pin)
            await handler.finish()

            if handler.has_paired:
                service = handler.service
                if service.credentials:
                    self.credentials.set(identifier, protocol.name, service.credentials)
                return True
            return False
        finally:
            await handler.close()
            self._pairing_handlers.pop(handler_key, None)

    async def connect(
        self,
        identifier: str,
        address: str,
        name: str,
        protocol: Protocol = Protocol.AirPlay,
    ) -> AppleTVInterface:
        """Connect to a specific AirPlay device."""
        device_config = conf.AppleTV(
            address=ipaddress.IPv4Address(address),
            name=name,
        )

        if protocol == Protocol.AirPlay:
            service = conf.AirPlayService(identifier, port=7000)
            creds = self.credentials.get(identifier, "AirPlay")
            if creds:
                service.credentials = creds
        elif protocol == Protocol.Companion:
            service = conf.CompanionService(port=49153)
            creds = self.credentials.get(identifier, "Companion")
            if creds:
                service.credentials = creds
        else:
            service = conf.AirPlayService(identifier, port=7000)

        device_config.add_service(service)

        atv = await connect(device_config)
        self.devices[identifier] = atv
        return atv

    async def connect_by_name(
        self, name: str, protocol: Protocol = Protocol.AirPlay
    ) -> AppleTVInterface:
        """Connect to a device by its name."""
        devices = await self.scan()
        for dev in devices:
            if dev["name"] == name:
                return await self.connect(
                    dev["identifier"], dev["address"], dev["name"], protocol
                )
        raise ValueError(f"Device '{name}' not found")

    async def disconnect(self, identifier: str):
        """Disconnect from a device."""
        if identifier in self.devices:
            await self.devices[identifier].close()
            del self.devices[identifier]

    async def disconnect_all(self):
        """Disconnect from all devices."""
        for identifier in list(self.devices.keys()):
            await self.disconnect(identifier)

    async def power_on(self, identifier: str):
        """Turn on a device."""
        atv = self._get_device(identifier)
        await atv.power.turn_on()

    async def power_off(self, identifier: str):
        """Turn off a device."""
        atv = self._get_device(identifier)
        await atv.power.turn_off()

    async def get_power_state(self, identifier: str):
        """Get power state of a device."""
        atv = self._get_device(identifier)
        return atv.power.power_state

    async def play(self, identifier: str):
        """Play/Resume playback."""
        atv = self._get_device(identifier)
        await atv.remote_control.play()

    async def pause(self, identifier: str):
        """Pause playback."""
        atv = self._get_device(identifier)
        await atv.remote_control.pause()

    async def stop(self, identifier: str):
        """Stop playback."""
        atv = self._get_device(identifier)
        await atv.remote_control.stop()

    async def play_url(self, identifier: str, url: str, **kwargs):
        """Play a URL (video or audio). Only http/https URLs are allowed."""
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_URL_SCHEMES:
            raise ValueError(
                f"URL scheme '{parsed.scheme}' not allowed. Use http or https."
            )
        if not parsed.hostname:
            raise ValueError("URL must include a hostname.")
        atv = self._get_device(identifier)
        await atv.stream.play_url(url, **kwargs)

    async def stream_file(self, identifier: str, file_path: str):
        """Stream a local media file to the device."""
        path = Path(file_path).resolve()
        if path.is_symlink():
            real = Path(os.path.realpath(path))
            if real != path:
                raise ValueError("Symlinks are not allowed for streaming.")
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        if path.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{path.suffix}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_MEDIA_EXTENSIONS))}"
            )
        atv = self._get_device(identifier)
        await atv.stream.stream_file(str(path))

    async def set_volume(self, identifier: str, volume: float):
        """Set volume (0.0 to 1.0)."""
        if not isinstance(volume, (int, float)) or math.isnan(volume) or math.isinf(volume):
            raise ValueError("Volume must be a finite number.")
        if not (0.0 <= volume <= 1.0):
            raise ValueError(f"Volume must be between 0.0 and 1.0, got {volume}")
        atv = self._get_device(identifier)
        await atv.audio.set_volume(volume)

    async def volume_up(self, identifier: str, delta: float = 0.1):
        """Increase volume by delta."""
        self._validate_delta(delta)
        atv = self._get_device(identifier)
        current = atv.audio.volume
        await atv.audio.set_volume(min(1.0, current + delta))

    async def volume_down(self, identifier: str, delta: float = 0.1):
        """Decrease volume by delta."""
        self._validate_delta(delta)
        atv = self._get_device(identifier)
        current = atv.audio.volume
        await atv.audio.set_volume(max(0.0, current - delta))

    async def get_volume(self, identifier: str) -> float:
        """Get current volume."""
        atv = self._get_device(identifier)
        return atv.audio.volume

    async def now_playing(self, identifier: str) -> dict:
        """Get now playing information."""
        atv = self._get_device(identifier)
        playing = await atv.metadata.playing()
        return {
            "media_type": playing.media_type.name,
            "device_state": playing.device_state.name,
            "title": playing.title,
            "artist": playing.artist,
            "album": playing.album,
            "position": playing.position,
            "total_time": playing.total_time,
        }

    async def seek(self, identifier: str, position: float):
        """Seek to position in seconds."""
        atv = self._get_device(identifier)
        await atv.remote_control.set_position(position)

    async def send_key(self, identifier: str, key: str):
        """Send a key press."""
        atv = self._get_device(identifier)
        from pyatv.const import Key

        key_map = {
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "select": Key.select,
            "menu": Key.menu,
            "home": Key.home,
            "play": Key.play,
            "pause": Key.pause,
            "play_pause": Key.play_pause,
            "next": Key.next,
            "previous": Key.previous,
        }
        if key not in key_map:
            raise ValueError(f"Unknown key: {key}")
        await atv.remote_control.keypress(key_map[key])

    def _get_device(self, identifier: str) -> AppleTVInterface:
        if identifier not in self.devices:
            raise ValueError(f"Device '{identifier}' not connected")
        return self.devices[identifier]

    @staticmethod
    def _validate_delta(delta: float):
        if not isinstance(delta, (int, float)) or math.isnan(delta) or math.isinf(delta):
            raise ValueError("Delta must be a finite number.")
        if not (0.0 < delta <= 1.0):
            raise ValueError(f"Delta must be between 0.0 and 1.0, got {delta}")

    def get_tool_definitions(self) -> list[dict]:
        """Get LLM tool definitions for this agent."""
        return get_tool_definitions()
