"""CastMasta unified agent for AirPlay and Google Cast devices."""

import asyncio
import ipaddress
import logging
import math
import os
import re
import shutil
import sys
import tempfile
import wave
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import pyatv
import pychromecast
from pyatv.const import Protocol

from .airplay_backend import AirPlayBackend
from .backend import DeviceBackend
from .cast_backend import GoogleCastBackend
from .config import AgentConfig
from .credentials import CredentialStore
from .tools import get_tool_definitions

logger = logging.getLogger(__name__)

ALLOWED_MEDIA_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".ogg", ".mp4", ".m4a", ".aac", ".m4v", ".mov",
}

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}

ALLOWED_URL_SCHEMES = {"http", "https"}

MAX_SCAN_TIMEOUT = 30
MIN_DISPLAY_DURATION = 1
MAX_DISPLAY_DURATION = 86400

_USER_VOICE_DIR = Path.home() / ".local/share/piper-voices"
_SYSTEM_VOICE_DIR = Path("/usr/share/castmasta/voices")
PIPER_VOICE_DATA_DIR = _USER_VOICE_DIR if _USER_VOICE_DIR.exists() else _SYSTEM_VOICE_DIR
DEFAULT_VOICE = "en_US-lessac-medium"
MAX_ANNOUNCE_TEXT_LEN = 4000
_VOICE_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")
PIPER_BIN = shutil.which("piper") or str(Path(sys.executable).parent / "piper")


def _prepend_silence(wav_path: str, seconds: float = 1.5) -> None:
    """Prepend silence to a WAV file in-place to absorb RAOP stream startup latency."""
    with wave.open(wav_path, "rb") as src:
        params = src.getparams()
        audio = src.readframes(src.getnframes())
    silence_frames = int(params.framerate * seconds)
    silence = b"\x00" * silence_frames * params.nchannels * params.sampwidth
    with wave.open(wav_path, "wb") as dst:
        dst.setparams(params)
        dst.writeframes(silence + audio)


class CastAgent:
    """Unified agent for controlling AirPlay and Google Cast devices."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.devices: dict[str, DeviceBackend] = {}
        self.credentials = CredentialStore(self.config.storage_path)
        self._pairing_handlers: dict[str, object] = {}
        self._last_scan: list[dict] = []

    async def scan(self, timeout: int = 10) -> list[dict]:
        timeout = max(1, min(timeout, MAX_SCAN_TIMEOUT))
        airplay_devices, cast_devices = await asyncio.gather(
            self._scan_airplay(timeout),
            self._scan_cast(timeout),
        )
        self._last_scan = airplay_devices + cast_devices
        return self._last_scan

    async def _scan_airplay(self, timeout: int) -> list[dict]:
        try:
            atvs = await pyatv.scan(loop=asyncio.get_event_loop(), timeout=timeout)
            results = []
            for atv in atvs:
                services = atv.services if hasattr(atv, "services") else []
                results.append({
                    "name": atv.name,
                    "address": str(atv.address),
                    "identifier": atv.identifier,
                    "device_type": "airplay",
                    "protocols": [s.protocol.name for s in services],
                })
            return results
        except Exception:
            logger.exception("AirPlay scan failed")
            return []

    async def _scan_cast(self, timeout: int) -> list[dict]:
        try:
            chromecasts, browser = await asyncio.to_thread(
                pychromecast.get_chromecasts, timeout=timeout,
            )
            await asyncio.to_thread(browser.stop_discovery)
            results = []
            for cc in chromecasts:
                results.append({
                    "name": cc.cast_info.friendly_name,
                    "address": str(cc.cast_info.host),
                    "identifier": str(cc.uuid),
                    "device_type": "googlecast",
                    "protocols": ["googlecast"],
                })
            return results
        except Exception:
            logger.exception("Google Cast scan failed")
            return []

    def _resolve_device_type(self, identifier: str) -> Optional[str]:
        for dev in self._last_scan:
            if dev["identifier"] == identifier:
                return dev["device_type"]
        return None

    async def connect(
        self, identifier: str, address: str, name: str,
        protocol: Protocol = Protocol.AirPlay,
        device_type: Optional[str] = None,
    ) -> DeviceBackend:
        if device_type is None:
            device_type = self._resolve_device_type(identifier)
        if device_type is None:
            device_type = "airplay"

        if device_type == "googlecast":
            backend = GoogleCastBackend(
                file_server_port=self.config.cast_file_server_port,
            )
            await backend.connect(identifier, address, name)
        else:
            backend = AirPlayBackend(credentials=self.credentials)
            await backend.connect(identifier, address, name, protocol=protocol)

        self.devices[identifier] = backend
        return backend

    async def connect_by_name(
        self, name: str, protocol: Protocol = Protocol.AirPlay,
    ) -> DeviceBackend:
        devices = await self.scan()
        for dev in devices:
            if dev["name"] == name:
                return await self.connect(
                    dev["identifier"], dev["address"], dev["name"],
                    protocol=protocol, device_type=dev["device_type"],
                )
        raise ValueError(f"Device '{name}' not found")

    async def disconnect(self, identifier: str):
        if identifier in self.devices:
            await self.devices[identifier].disconnect()
            del self.devices[identifier]

    async def disconnect_all(self):
        for identifier in list(self.devices.keys()):
            await self.disconnect(identifier)

    def _get_backend(self, identifier: str) -> DeviceBackend:
        if identifier not in self.devices:
            raise ValueError(f"Device '{identifier}' not connected")
        return self.devices[identifier]

    # --- Pairing (AirPlay-only) ---

    async def pair(
        self, identifier: str, address: str, name: str,
        protocol: Protocol = Protocol.AirPlay,
    ) -> dict:
        device_type = self._resolve_device_type(identifier)
        if device_type == "googlecast":
            raise ValueError("Pairing is not required for Google Cast devices.")

        from pyatv import conf, pair as pyatv_pair
        device_config = conf.AppleTV(
            address=ipaddress.IPv4Address(address), name=name,
        )
        if protocol == Protocol.AirPlay:
            service = conf.AirPlayService(identifier, port=7000)
        elif protocol == Protocol.Companion:
            service = conf.CompanionService(port=49153)
        else:
            raise ValueError(f"Unsupported protocol for pairing: {protocol}")

        device_config.add_service(service)
        handler = await pyatv_pair(device_config, protocol, loop=asyncio.get_event_loop())
        await handler.begin()

        handler_key = f"{identifier}:{protocol.name}"
        self._pairing_handlers[handler_key] = handler

        if not handler.device_provides_pin:
            return {"status": "pin_required", "message": "Enter PIN on the device itself"}
        return {"status": "ready", "message": "PIN required - use pair_with_pin method"}

    async def pair_with_pin(
        self, identifier: str, address: str, name: str, pin: str,
        protocol: Protocol = Protocol.AirPlay,
    ) -> bool:
        handler_key = f"{identifier}:{protocol.name}"
        handler = self._pairing_handlers.get(handler_key)
        if handler is None:
            raise ValueError(f"No active pairing session for {identifier}. Call pair() first.")

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

    # --- Power ---

    async def power_on(self, identifier: str):
        await self._get_backend(identifier).power_on()

    async def power_off(self, identifier: str):
        await self._get_backend(identifier).power_off()

    async def get_power_state(self, identifier: str):
        return await self._get_backend(identifier).get_power_state()

    # --- Playback ---

    async def play(self, identifier: str):
        await self._get_backend(identifier).play()

    async def pause(self, identifier: str):
        await self._get_backend(identifier).pause()

    async def stop(self, identifier: str):
        await self._get_backend(identifier).stop()

    async def play_url(self, identifier: str, url: str, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_URL_SCHEMES:
            raise ValueError(f"URL scheme '{parsed.scheme}' not allowed. Use http or https.")
        if not parsed.hostname:
            raise ValueError("URL must include a hostname.")
        await self._get_backend(identifier).play_url(url, **kwargs)

    async def stream_file(self, identifier: str, file_path: str):
        path = self._validate_media_file(file_path)
        await self._get_backend(identifier).stream_file(str(path))

    async def display_image(self, identifier: str, image_path: str, duration: int = 3600):
        if not isinstance(duration, (int, float)) or math.isnan(duration) or math.isinf(duration):
            raise ValueError("Duration must be a finite number.")
        duration = max(MIN_DISPLAY_DURATION, min(int(duration), MAX_DISPLAY_DURATION))

        path = self._validate_image_file(image_path)
        backend = self._get_backend(identifier)

        fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        os.chmod(tmp_path, 0o600)
        try:
            # Using create_subprocess_exec (not shell) for safety - no injection risk
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-loop", "1", "-i", str(path),
                "-c:v", "libx264", "-t", str(duration),
                "-pix_fmt", "yuv420p", "-y", tmp_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg failed (exit {proc.returncode}): {stderr.decode(errors='replace')}"
                )
            await backend.stream_file(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def announce(
        self, identifier: str, text: str, voice: str = DEFAULT_VOICE,
    ) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string.")
        if len(text) > MAX_ANNOUNCE_TEXT_LEN:
            raise ValueError(f"text too long (max {MAX_ANNOUNCE_TEXT_LEN} chars).")
        if not voice or not _VOICE_RE.match(voice):
            raise ValueError("voice must be a simple model name (letters, digits, hyphens, underscores only).")

        backend = self._get_backend(identifier)

        # Wake AirPlay device and reset its auto-off timer before streaming.
        if backend.device_type == "airplay":
            try:
                await backend.send_key("menu")
            except Exception:
                pass

        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        os.chmod(tmp_path, 0o600)
        try:
            proc = await asyncio.create_subprocess_exec(
                PIPER_BIN,
                "--model", voice,
                "--data-dir", str(PIPER_VOICE_DATA_DIR),
                "--output_file", tmp_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(input=text.encode())
            if proc.returncode != 0:
                raise RuntimeError(
                    f"piper failed (exit {proc.returncode}): {stderr.decode(errors='replace')}"
                )
            _prepend_silence(tmp_path)
            await backend.stream_file(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # --- Volume ---

    async def set_volume(self, identifier: str, volume: float):
        self._validate_volume(volume)
        await self._get_backend(identifier).set_volume(volume)

    async def volume_up(self, identifier: str, delta: float = 0.1):
        self._validate_delta(delta)
        backend = self._get_backend(identifier)
        current = await backend.get_volume()
        await backend.set_volume(min(1.0, current + delta))

    async def volume_down(self, identifier: str, delta: float = 0.1):
        self._validate_delta(delta)
        backend = self._get_backend(identifier)
        current = await backend.get_volume()
        await backend.set_volume(max(0.0, current - delta))

    async def get_volume(self, identifier: str) -> float:
        return await self._get_backend(identifier).get_volume()

    # --- Info ---

    async def now_playing(self, identifier: str) -> dict:
        return await self._get_backend(identifier).now_playing()

    async def seek(self, identifier: str, position: float):
        await self._get_backend(identifier).seek(position)

    # --- Remote (AirPlay-only) ---

    async def send_key(self, identifier: str, key: str):
        backend = self._get_backend(identifier)
        if backend.device_type != "airplay":
            raise ValueError("send_key is not supported on Google Cast devices.")
        await backend.send_key(key)

    # --- Validation helpers ---

    def _validate_media_file(self, file_path: str) -> Path:
        unresolved = Path(file_path)
        if unresolved.is_symlink():
            raise ValueError("Symlinks are not allowed for streaming.")
        path = unresolved.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        if path.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{path.suffix}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_MEDIA_EXTENSIONS))}"
            )
        return path

    def _validate_image_file(self, image_path: str) -> Path:
        unresolved = Path(image_path)
        if unresolved.is_symlink():
            raise ValueError("Symlinks are not allowed for image display.")
        path = unresolved.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(
                f"Unsupported image type '{path.suffix}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
            )
        return path

    @staticmethod
    def _validate_volume(volume: float):
        if isinstance(volume, bool) or not isinstance(volume, (int, float)) or math.isnan(volume) or math.isinf(volume):
            raise ValueError("Volume must be a finite number.")
        if not (0.0 <= volume <= 1.0):
            raise ValueError(f"Volume must be between 0.0 and 1.0, got {volume}")

    @staticmethod
    def _validate_delta(delta: float):
        if isinstance(delta, bool) or not isinstance(delta, (int, float)) or math.isnan(delta) or math.isinf(delta):
            raise ValueError("Delta must be a finite number.")
        if not (0.0 < delta <= 1.0):
            raise ValueError(f"Delta must be between 0.0 and 1.0, got {delta}")

    def get_tool_definitions(self) -> list[dict]:
        return get_tool_definitions()
