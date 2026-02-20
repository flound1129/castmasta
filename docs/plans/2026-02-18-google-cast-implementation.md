# CastMasta: Google Cast + AirPlay Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename `airplay_agent` to `castmasta` and add Google Cast support via a unified backend pattern, so one set of CLI/MCP/tool commands controls both AirPlay and Chromecast devices.

**Architecture:** `DeviceBackend` ABC with `AirPlayBackend` (wraps pyatv) and `GoogleCastBackend` (wraps pychromecast). `CastAgent` facade dispatches to the correct backend by device identifier. Local file streaming to Cast uses an aiohttp HTTP server on a fixed configurable port (default 8089).

**Tech Stack:** Python 3.10+, pyatv, pychromecast, aiohttp, click, fastmcp, pytest

---

### Task 1: Create `castmasta/` package skeleton

**Files:**
- Create: `castmasta/__init__.py`
- Create: `castmasta/config.py`
- Create: `castmasta/credentials.py`
- Create: `tests/test_credentials.py`

**Step 1: Create `castmasta/__init__.py`**

```python
"""CastMasta - LLM agent for controlling AirPlay and Google Cast devices."""

from .agent import CastAgent
from .config import AgentConfig, DeviceConfig

__version__ = "0.2.0"
__all__ = ["CastAgent", "AgentConfig", "DeviceConfig"]
```

Note: This will fail to import until `agent.py` exists (Task 6). That's expected.

**Step 2: Create `castmasta/config.py`**

Copy from `airplay_agent/config.py` and add `cast_file_server_port`:

```python
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
```

**Step 3: Create `castmasta/credentials.py`**

Extract `CredentialStore` from `airplay_agent/agent.py` (lines 35-95). Update the default path from `.airplay-agent` to `.castmasta`:

```python
"""Credential storage for device pairing."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CredentialStore:
    """Store and retrieve device credentials."""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".castmasta" / "credentials.json"
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
        key = f"{identifier}:{protocol}"
        return self._credentials.get(key)

    def set(self, identifier: str, protocol: str, credentials: str):
        key = f"{identifier}:{protocol}"
        self._credentials[key] = credentials
        self._save()

    def delete(self, identifier: str, protocol: Optional[str] = None):
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
```

**Step 4: Write tests for CredentialStore**

Create `tests/test_credentials.py`:

```python
import os
import pytest
from castmasta.credentials import CredentialStore


@pytest.fixture
def cred_store(tmp_path):
    path = str(tmp_path / "creds.json")
    return CredentialStore(storage_path=path)


def test_set_and_get(cred_store):
    cred_store.set("dev1", "AirPlay", "secret123")
    assert cred_store.get("dev1", "AirPlay") == "secret123"


def test_get_missing(cred_store):
    assert cred_store.get("nonexistent", "AirPlay") is None


def test_delete_specific_protocol(cred_store):
    cred_store.set("dev1", "AirPlay", "secret1")
    cred_store.set("dev1", "Companion", "secret2")
    cred_store.delete("dev1", "AirPlay")
    assert cred_store.get("dev1", "AirPlay") is None
    assert cred_store.get("dev1", "Companion") == "secret2"


def test_delete_all_protocols(cred_store):
    cred_store.set("dev1", "AirPlay", "secret1")
    cred_store.set("dev1", "Companion", "secret2")
    cred_store.delete("dev1")
    assert cred_store.get("dev1", "AirPlay") is None
    assert cred_store.get("dev1", "Companion") is None


def test_persistence(tmp_path):
    path = str(tmp_path / "creds.json")
    store1 = CredentialStore(storage_path=path)
    store1.set("dev1", "AirPlay", "secret123")
    store2 = CredentialStore(storage_path=path)
    assert store2.get("dev1", "AirPlay") == "secret123"


def test_file_permissions(tmp_path):
    path = str(tmp_path / "creds.json")
    store = CredentialStore(storage_path=path)
    store.set("dev1", "AirPlay", "secret123")
    stat = os.stat(path)
    assert oct(stat.st_mode & 0o777) == "0o600"
```

**Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_credentials.py -v`
Expected: All 6 tests PASS

**Step 6: Commit**

```
git add castmasta/__init__.py castmasta/config.py castmasta/credentials.py tests/test_credentials.py
git commit -m "feat: create castmasta package skeleton with config and credentials"
```

---

### Task 2: Create `DeviceBackend` ABC

**Files:**
- Create: `castmasta/backend.py`
- Create: `tests/test_backend.py`

**Step 1: Write `castmasta/backend.py`**

```python
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
```

**Step 2: Write test**

Create `tests/test_backend.py`:

```python
import pytest
from castmasta.backend import DeviceBackend


def test_cannot_instantiate_abc():
    with pytest.raises(TypeError, match="abstract"):
        DeviceBackend()
```

**Step 3: Run test**

Run: `.venv/bin/pytest tests/test_backend.py -v`
Expected: PASS

**Step 4: Commit**

```
git add castmasta/backend.py tests/test_backend.py
git commit -m "feat: add DeviceBackend abstract base class"
```

---

### Task 3: Create `AirPlayBackend`

**Files:**
- Create: `castmasta/airplay_backend.py`
- Create: `tests/test_airplay_backend.py`

**Step 1: Write tests (mocking pyatv)**

Create `tests/test_airplay_backend.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from castmasta.airplay_backend import AirPlayBackend


@pytest.fixture
def backend():
    return AirPlayBackend()


@pytest.fixture
def mock_atv():
    atv = AsyncMock()
    atv.stream = AsyncMock()
    atv.remote_control = AsyncMock()
    atv.audio = MagicMock()
    atv.audio.volume = 0.5
    atv.power = AsyncMock()
    atv.metadata = AsyncMock()
    atv.close = AsyncMock()
    return atv


@pytest.mark.asyncio
async def test_device_type(backend):
    assert backend.device_type == "airplay"


@pytest.mark.asyncio
async def test_connect(backend):
    with patch("castmasta.airplay_backend.pyatv_connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = AsyncMock()
        await backend.connect("id1", "192.168.1.100", "Test TV")
        assert backend._atv is not None


@pytest.mark.asyncio
async def test_disconnect(backend):
    backend._atv = AsyncMock()
    await backend.disconnect()
    backend._atv is None


@pytest.mark.asyncio
async def test_play(backend, mock_atv):
    backend._atv = mock_atv
    await backend.play()
    mock_atv.remote_control.play.assert_called_once()


@pytest.mark.asyncio
async def test_pause(backend, mock_atv):
    backend._atv = mock_atv
    await backend.pause()
    mock_atv.remote_control.pause.assert_called_once()


@pytest.mark.asyncio
async def test_stop(backend, mock_atv):
    backend._atv = mock_atv
    await backend.stop()
    mock_atv.remote_control.stop.assert_called_once()


@pytest.mark.asyncio
async def test_set_volume(backend, mock_atv):
    backend._atv = mock_atv
    await backend.set_volume(0.7)
    mock_atv.audio.set_volume.assert_called_once_with(0.7)


@pytest.mark.asyncio
async def test_get_volume(backend, mock_atv):
    backend._atv = mock_atv
    vol = await backend.get_volume()
    assert vol == 0.5


@pytest.mark.asyncio
async def test_stream_file(backend, mock_atv):
    backend._atv = mock_atv
    await backend.stream_file("/tmp/test.mp4")
    mock_atv.stream.stream_file.assert_called_once_with("/tmp/test.mp4")


@pytest.mark.asyncio
async def test_play_url(backend, mock_atv):
    backend._atv = mock_atv
    await backend.play_url("http://example.com/video.mp4")
    mock_atv.stream.play_url.assert_called_once_with("http://example.com/video.mp4")


@pytest.mark.asyncio
async def test_seek(backend, mock_atv):
    backend._atv = mock_atv
    await backend.seek(30.0)
    mock_atv.remote_control.set_position.assert_called_once_with(30.0)
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_airplay_backend.py -v`
Expected: FAIL (module not found)

**Step 3: Write `castmasta/airplay_backend.py`**

```python
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
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_airplay_backend.py -v`
Expected: All PASS

**Step 5: Commit**

```
git add castmasta/airplay_backend.py tests/test_airplay_backend.py
git commit -m "feat: add AirPlayBackend extracted from AirPlayAgent"
```

---

### Task 4: Create HTTP file server for Cast

**Files:**
- Create: `castmasta/file_server.py`
- Create: `tests/test_file_server.py`

**Step 1: Write tests**

Create `tests/test_file_server.py`:

```python
import pytest
import aiohttp
from castmasta.file_server import FileServer


@pytest.fixture
def media_file(tmp_path):
    f = tmp_path / "test.mp4"
    f.write_bytes(b"fake mp4 content")
    return str(f)


@pytest.mark.asyncio
async def test_server_starts_and_serves_file(media_file):
    server = FileServer(port=18089)
    url = await server.serve_file(media_file)
    assert "18089" in url
    assert url.startswith("http://")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            assert resp.status == 200
            body = await resp.read()
            assert body == b"fake mp4 content"

    await server.shutdown()


@pytest.mark.asyncio
async def test_server_404_for_wrong_path(media_file):
    server = FileServer(port=18090)
    await server.serve_file(media_file)

    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:18090/wrong") as resp:
            assert resp.status == 404

    await server.shutdown()


@pytest.mark.asyncio
async def test_server_shutdown_is_idempotent(media_file):
    server = FileServer(port=18091)
    await server.serve_file(media_file)
    await server.shutdown()
    await server.shutdown()  # should not raise
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_file_server.py -v`
Expected: FAIL (module not found)

**Step 3: Write `castmasta/file_server.py`**

```python
"""HTTP file server for streaming local files to Google Cast devices."""

import logging
import mimetypes
import os
import socket
from pathlib import Path

from aiohttp import web

logger = logging.getLogger(__name__)


def _get_local_ip() -> str:
    """Get the local IP address that can reach the LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


class FileServer:
    """Lightweight HTTP server that serves a single file for Cast devices."""

    def __init__(self, port: int = 8089):
        self._port = port
        self._runner = None
        self._file_path: str | None = None
        self._file_name: str | None = None

    async def serve_file(self, file_path: str) -> str:
        """Start serving a file. Returns the URL to access it."""
        self._file_path = file_path
        self._file_name = Path(file_path).name

        app = web.Application()
        app.router.add_get("/media/{filename}", self._handle_media)
        app.router.add_get("/{tail:.*}", self._handle_404)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()

        local_ip = _get_local_ip()
        url = f"http://{local_ip}:{self._port}/media/{self._file_name}"
        logger.info("File server started at %s", url)
        return url

    async def _handle_media(self, request: web.Request) -> web.StreamResponse:
        filename = request.match_info["filename"]
        if filename != self._file_name or not self._file_path:
            return web.Response(status=404)

        content_type = mimetypes.guess_type(self._file_path)[0] or "application/octet-stream"
        file_size = os.path.getsize(self._file_path)

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
            },
        )
        await response.prepare(request)

        with open(self._file_path, "rb") as f:
            while chunk := f.read(65536):
                await response.write(chunk)

        return response

    async def _handle_404(self, request: web.Request) -> web.Response:
        return web.Response(status=404)

    async def shutdown(self):
        """Stop the file server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._file_path = None
            self._file_name = None
            logger.info("File server stopped")
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_file_server.py -v`
Expected: All PASS

**Step 5: Commit**

```
git add castmasta/file_server.py tests/test_file_server.py
git commit -m "feat: add HTTP file server for Google Cast local streaming"
```

---

### Task 5: Create `GoogleCastBackend`

**Files:**
- Create: `castmasta/cast_backend.py`
- Create: `tests/test_cast_backend.py`

**Step 1: Write tests (mocking pychromecast)**

Create `tests/test_cast_backend.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from castmasta.cast_backend import GoogleCastBackend


@pytest.fixture
def mock_cast_device():
    cast = MagicMock()
    cast.uuid = "test-uuid-123"
    cast.name = "Living Room"
    cast.host = "192.168.1.50"
    cast.port = 8009
    cast.wait = MagicMock()
    cast.disconnect = MagicMock()
    cast.quit_app = MagicMock()
    cast.set_volume = MagicMock()

    status = MagicMock()
    status.volume_level = 0.5
    cast.status = status

    mc = MagicMock()
    mc.play = MagicMock()
    mc.pause = MagicMock()
    mc.stop = MagicMock()
    mc.seek = MagicMock()
    mc.play_media = MagicMock()
    mc.block_until_active = MagicMock()

    mc_status = MagicMock()
    mc_status.title = "Test Song"
    mc_status.artist = "Test Artist"
    mc_status.album_name = "Test Album"
    mc_status.current_time = 30.0
    mc_status.duration = 180.0
    mc_status.player_state = "PLAYING"
    mc_status.media_type = "GENERIC"
    mc.status = mc_status

    cast.media_controller = mc
    return cast


@pytest.fixture
def backend():
    return GoogleCastBackend(file_server_port=18095)


@pytest.mark.asyncio
async def test_device_type(backend):
    assert backend.device_type == "googlecast"


@pytest.mark.asyncio
async def test_play(backend, mock_cast_device):
    backend._cast = mock_cast_device
    await backend.play()
    mock_cast_device.media_controller.play.assert_called_once()


@pytest.mark.asyncio
async def test_pause(backend, mock_cast_device):
    backend._cast = mock_cast_device
    await backend.pause()
    mock_cast_device.media_controller.pause.assert_called_once()


@pytest.mark.asyncio
async def test_stop(backend, mock_cast_device):
    backend._cast = mock_cast_device
    await backend.stop()
    mock_cast_device.media_controller.stop.assert_called_once()


@pytest.mark.asyncio
async def test_seek(backend, mock_cast_device):
    backend._cast = mock_cast_device
    await backend.seek(60.0)
    mock_cast_device.media_controller.seek.assert_called_once_with(60.0)


@pytest.mark.asyncio
async def test_set_volume(backend, mock_cast_device):
    backend._cast = mock_cast_device
    await backend.set_volume(0.7)
    mock_cast_device.set_volume.assert_called_once_with(0.7)


@pytest.mark.asyncio
async def test_get_volume(backend, mock_cast_device):
    backend._cast = mock_cast_device
    vol = await backend.get_volume()
    assert vol == 0.5


@pytest.mark.asyncio
async def test_now_playing(backend, mock_cast_device):
    backend._cast = mock_cast_device
    info = await backend.now_playing()
    assert info["title"] == "Test Song"
    assert info["artist"] == "Test Artist"
    assert info["position"] == 30.0
    assert info["total_time"] == 180.0


@pytest.mark.asyncio
async def test_play_url(backend, mock_cast_device):
    backend._cast = mock_cast_device
    await backend.play_url("http://example.com/video.mp4")
    mock_cast_device.media_controller.play_media.assert_called_once()


@pytest.mark.asyncio
async def test_power_off_quits_app(backend, mock_cast_device):
    backend._cast = mock_cast_device
    await backend.power_off()
    mock_cast_device.quit_app.assert_called_once()


@pytest.mark.asyncio
async def test_power_on_is_noop(backend, mock_cast_device):
    backend._cast = mock_cast_device
    await backend.power_on()  # should not raise


@pytest.mark.asyncio
async def test_get_power_state(backend, mock_cast_device):
    backend._cast = mock_cast_device
    state = await backend.get_power_state()
    assert state is True
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cast_backend.py -v`
Expected: FAIL (module not found)

**Step 3: Write `castmasta/cast_backend.py`**

```python
"""Google Cast backend using pychromecast."""

import asyncio
import logging
import mimetypes
from typing import Optional

import pychromecast

from .backend import DeviceBackend
from .file_server import FileServer

logger = logging.getLogger(__name__)


class GoogleCastBackend(DeviceBackend):
    """Backend for Google Cast devices (Chromecast, Google Home, etc.)."""

    device_type = "googlecast"

    def __init__(self, file_server_port: int = 8089):
        self._cast = None
        self._browser = None
        self._file_server = FileServer(port=file_server_port)
        self._file_server_port = file_server_port

    async def connect(self, identifier: str, address: str, name: str, **kwargs) -> None:
        chromecasts, browser = await asyncio.to_thread(
            pychromecast.get_listed_chromecasts,
            friendly_names=[name],
        )
        self._browser = browser

        for cc in chromecasts:
            if str(cc.uuid) == identifier or cc.name == name:
                self._cast = cc
                await asyncio.to_thread(cc.wait)
                logger.info("Connected to Google Cast device: %s", name)
                return

        if browser:
            browser.stop_discovery()
        raise ValueError(f"Google Cast device '{name}' not found")

    async def disconnect(self) -> None:
        await self._file_server.shutdown()
        if self._cast:
            await asyncio.to_thread(self._cast.disconnect)
            self._cast = None
        if self._browser:
            self._browser.stop_discovery()
            self._browser = None

    async def stream_file(self, file_path: str) -> None:
        url = await self._file_server.serve_file(file_path)
        content_type = mimetypes.guess_type(file_path)[0] or "video/mp4"
        mc = self._cast.media_controller
        await asyncio.to_thread(mc.play_media, url, content_type)
        await asyncio.to_thread(mc.block_until_active)

    async def play_url(self, url: str, **kwargs) -> None:
        content_type = kwargs.get("content_type", "video/mp4")
        mc = self._cast.media_controller
        await asyncio.to_thread(mc.play_media, url, content_type)
        await asyncio.to_thread(mc.block_until_active)

    async def play(self) -> None:
        await asyncio.to_thread(self._cast.media_controller.play)

    async def pause(self) -> None:
        await asyncio.to_thread(self._cast.media_controller.pause)

    async def stop(self) -> None:
        await asyncio.to_thread(self._cast.media_controller.stop)
        await self._file_server.shutdown()

    async def seek(self, position: float) -> None:
        await asyncio.to_thread(self._cast.media_controller.seek, position)

    async def set_volume(self, volume: float) -> None:
        await asyncio.to_thread(self._cast.set_volume, volume)

    async def get_volume(self) -> float:
        return self._cast.status.volume_level

    async def now_playing(self) -> dict:
        mc = self._cast.media_controller
        status = mc.status
        return {
            "media_type": getattr(status, "media_type", "Unknown"),
            "device_state": getattr(status, "player_state", "Unknown"),
            "title": getattr(status, "title", None),
            "artist": getattr(status, "artist", None),
            "album": getattr(status, "album_name", None),
            "position": getattr(status, "current_time", None),
            "total_time": getattr(status, "duration", None),
        }

    async def power_on(self) -> None:
        pass  # Cast devices are always on when reachable

    async def power_off(self) -> None:
        await asyncio.to_thread(self._cast.quit_app)

    async def get_power_state(self) -> bool:
        return self._cast is not None and self._cast.status is not None
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_cast_backend.py -v`
Expected: All PASS

**Step 5: Commit**

```
git add castmasta/cast_backend.py tests/test_cast_backend.py
git commit -m "feat: add GoogleCastBackend with pychromecast"
```

---

### Task 6: Create `CastAgent` unified facade

**Files:**
- Create: `castmasta/agent.py`
- Create: `tests/test_agent.py`

**Step 1: Write tests**

Create `tests/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from castmasta.agent import CastAgent
from castmasta.config import AgentConfig


@pytest.fixture
def agent(tmp_path):
    config = AgentConfig(storage_path=str(tmp_path / "creds.json"))
    return CastAgent(config)


@pytest.fixture
def mock_airplay_backend():
    backend = AsyncMock()
    backend.device_type = "airplay"
    backend.get_volume = AsyncMock(return_value=0.5)
    return backend


@pytest.fixture
def mock_cast_backend():
    backend = AsyncMock()
    backend.device_type = "googlecast"
    backend.get_volume = AsyncMock(return_value=0.5)
    return backend


@pytest.mark.asyncio
async def test_scan_merges_airplay_and_cast(agent):
    with patch("castmasta.agent.pyatv") as mock_pyatv, \
         patch("castmasta.agent.pychromecast") as mock_pcc:
        atv = MagicMock()
        atv.name = "Apple TV"
        atv.address = "192.168.1.10"
        atv.identifier = "airplay-id-1"
        atv.services = []
        mock_pyatv.scan = AsyncMock(return_value=[atv])

        cc = MagicMock()
        cc.name = "Chromecast"
        cc.host = "192.168.1.20"
        cc.uuid = "cast-uuid-1"
        cc.cast_type = "cast"
        browser = MagicMock()
        mock_pcc.get_chromecasts.return_value = ([cc], browser)

        devices = await agent.scan()
        assert len(devices) == 2
        types = {d["device_type"] for d in devices}
        assert types == {"airplay", "googlecast"}


def test_get_backend_not_connected(agent):
    with pytest.raises(ValueError, match="not connected"):
        agent._get_backend("nonexistent")


@pytest.mark.asyncio
async def test_play_dispatches_to_backend(agent, mock_airplay_backend):
    agent.devices["dev1"] = mock_airplay_backend
    await agent.play("dev1")
    mock_airplay_backend.play.assert_called_once()


@pytest.mark.asyncio
async def test_volume_up(agent, mock_airplay_backend):
    agent.devices["dev1"] = mock_airplay_backend
    await agent.volume_up("dev1", 0.2)
    mock_airplay_backend.set_volume.assert_called_once_with(0.7)


@pytest.mark.asyncio
async def test_volume_down(agent, mock_airplay_backend):
    agent.devices["dev1"] = mock_airplay_backend
    await agent.volume_down("dev1", 0.3)
    mock_airplay_backend.set_volume.assert_called_once_with(0.2)


@pytest.mark.asyncio
async def test_send_key_on_cast_raises(agent, mock_cast_backend):
    agent.devices["dev1"] = mock_cast_backend
    with pytest.raises(ValueError, match="not supported on Google Cast"):
        await agent.send_key("dev1", "up")


@pytest.mark.asyncio
async def test_send_key_on_airplay(agent, mock_airplay_backend):
    mock_airplay_backend.send_key = AsyncMock()
    agent.devices["dev1"] = mock_airplay_backend
    await agent.send_key("dev1", "up")
    mock_airplay_backend.send_key.assert_called_once_with("up")


def test_validate_volume_rejects_nan(agent):
    with pytest.raises(ValueError, match="finite number"):
        agent._validate_volume(float("nan"))


def test_validate_volume_rejects_out_of_range(agent):
    with pytest.raises(ValueError):
        agent._validate_volume(1.5)


@pytest.mark.asyncio
async def test_disconnect(agent, mock_airplay_backend):
    agent.devices["dev1"] = mock_airplay_backend
    await agent.disconnect("dev1")
    mock_airplay_backend.disconnect.assert_called_once()
    assert "dev1" not in agent.devices


@pytest.mark.asyncio
async def test_disconnect_all(agent, mock_airplay_backend, mock_cast_backend):
    agent.devices["dev1"] = mock_airplay_backend
    agent.devices["dev2"] = mock_cast_backend
    await agent.disconnect_all()
    assert len(agent.devices) == 0


@pytest.mark.asyncio
async def test_play_url_validates_scheme(agent, mock_airplay_backend):
    agent.devices["dev1"] = mock_airplay_backend
    with pytest.raises(ValueError, match="not allowed"):
        await agent.play_url("dev1", "ftp://example.com/file.mp4")


@pytest.mark.asyncio
async def test_stream_file_validates_extension(agent, mock_airplay_backend, tmp_path):
    agent.devices["dev1"] = mock_airplay_backend
    bad_file = tmp_path / "test.exe"
    bad_file.write_text("bad")
    with pytest.raises(ValueError, match="Unsupported file type"):
        await agent.stream_file("dev1", str(bad_file))
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_agent.py -v`
Expected: FAIL (module not found)

**Step 3: Write `castmasta/agent.py`**

This is the largest file. See the full implementation in the design document. Key points:

- Imports both `pyatv` and `pychromecast`
- `scan()` runs `_scan_airplay()` and `_scan_cast()` concurrently via `asyncio.gather()`
- `connect()` creates the correct backend based on `device_type` (resolved from scan cache)
- All playback/volume/power methods delegate to `self._get_backend(identifier)`
- `send_key()` checks `backend.device_type` and raises for Cast
- `pair()`/`pair_with_pin()` check device type and raise for Cast
- Validation helpers (`_validate_media_file`, `_validate_image_file`, `_validate_volume`, `_validate_delta`) are on the agent
- `display_image()` uses ffmpeg then calls `backend.stream_file()`

```python
"""CastMasta unified agent for AirPlay and Google Cast devices."""

import asyncio
import ipaddress
import logging
import math
import os
import tempfile
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


class CastAgent:
    """Unified agent for controlling AirPlay and Google Cast devices."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.devices: dict[str, DeviceBackend] = {}
        self.credentials = CredentialStore(self.config.storage_path)
        self._pairing_handlers: dict[str, object] = {}
        self._last_scan: list[dict] = []

    async def scan(self, timeout: int = 5) -> list[dict]:
        timeout = max(1, min(timeout, MAX_SCAN_TIMEOUT))
        airplay_devices, cast_devices = await asyncio.gather(
            self._scan_airplay(timeout),
            self._scan_cast(timeout),
        )
        self._last_scan = airplay_devices + cast_devices
        return self._last_scan

    async def _scan_airplay(self, timeout: int) -> list[dict]:
        try:
            atvs = await pyatv.scan(timeout=timeout)
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
            browser.stop_discovery()
            results = []
            for cc in chromecasts:
                results.append({
                    "name": cc.name,
                    "address": str(cc.host),
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
        handler = await pyatv_pair(device_config, protocol)
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
        return path

    def _validate_image_file(self, image_path: str) -> Path:
        path = Path(image_path).resolve()
        if path.is_symlink():
            real = Path(os.path.realpath(path))
            if real != path:
                raise ValueError("Symlinks are not allowed for image display.")
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
        if not isinstance(volume, (int, float)) or math.isnan(volume) or math.isinf(volume):
            raise ValueError("Volume must be a finite number.")
        if not (0.0 <= volume <= 1.0):
            raise ValueError(f"Volume must be between 0.0 and 1.0, got {volume}")

    @staticmethod
    def _validate_delta(delta: float):
        if not isinstance(delta, (int, float)) or math.isnan(delta) or math.isinf(delta):
            raise ValueError("Delta must be a finite number.")
        if not (0.0 < delta <= 1.0):
            raise ValueError(f"Delta must be between 0.0 and 1.0, got {delta}")

    def get_tool_definitions(self) -> list[dict]:
        return get_tool_definitions()
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_agent.py -v`
Expected: All PASS

**Step 5: Commit**

```
git add castmasta/agent.py tests/test_agent.py
git commit -m "feat: add CastAgent unified facade for AirPlay + Google Cast"
```

---

### Task 7: Create CLI for `castmasta`

**Files:**
- Create: `castmasta/cli.py`

**Step 1: Write `castmasta/cli.py`**

Same structure as `airplay_agent/cli.py` but uses `CastAgent`. Scan shows `device_type` tag. Connect auto-detects. See design doc for full code.

Key changes from the old CLI:
- Import `from castmasta import CastAgent`
- `scan` output: `{name} ({address}) [{device_type}]`
- `connect` output: `Connected to {name} [{backend.device_type}]`
- `pair`/`pair-pin` docstrings note "AirPlay only"
- `send-key` docstring notes "AirPlay only"

**Step 2: Syntax check**

Run: `python3 -c "import ast; ast.parse(open('castmasta/cli.py').read()); print('OK')"`
Expected: OK

**Step 3: Commit**

```
git add castmasta/cli.py
git commit -m "feat: add castmasta CLI with unified AirPlay + Cast commands"
```

---

### Task 8: Create MCP server for `castmasta`

**Files:**
- Create: `castmasta/mcp_server.py`

**Step 1: Write `castmasta/mcp_server.py`**

Same structure as `airplay_agent/mcp_server.py` but uses `CastAgent`. Scan shows `device_type`. Tool descriptions updated. See design doc for full code.

Key changes:
- `FastMCP("CastMasta")`
- `agent: CastAgent = CastAgent()`
- `scan_devices` description mentions both protocols
- `display_image` tool included
- `send_key` description notes "AirPlay only"
- `pair_device`/`pair_device_with_pin` descriptions note "AirPlay only", catch `ValueError` for Cast devices

**Step 2: Syntax check**

Run: `python3 -c "import ast; ast.parse(open('castmasta/mcp_server.py').read()); print('OK')"`
Expected: OK

**Step 3: Commit**

```
git add castmasta/mcp_server.py
git commit -m "feat: add castmasta MCP server with AirPlay + Cast support"
```

---

### Task 9: Create `tools.py` for `castmasta`

**Files:**
- Create: `castmasta/tools.py`

**Step 1: Write `castmasta/tools.py`**

Updated from `airplay_agent/tools.py`:
- `scan_airplay_devices` renamed to `scan_devices`, description mentions both protocols
- `connect_device` description updated for both protocols
- `display_image` tool included
- `send_key` description notes "AirPlay only"
- `power_off` description notes "quits app on Google Cast"

**Step 2: Syntax check**

Run: `python3 -c "import ast; ast.parse(open('castmasta/tools.py').read()); print('OK')"`
Expected: OK

**Step 3: Commit**

```
git add castmasta/tools.py
git commit -m "feat: add castmasta tool definitions for AirPlay + Cast"
```

---

### Task 10: Update `pyproject.toml` and remove old package

**Files:**
- Modify: `pyproject.toml`
- Delete: `airplay_agent/` directory
- Delete: `airplay_agent.egg-info/` directory

**Step 1: Update `pyproject.toml`**

Change:
- `name` to `"castmasta"`
- `version` to `"0.2.0"`
- `description` to `"LLM agent for controlling AirPlay and Google Cast devices"`
- Add `"pychromecast>=14.0.0"` to dependencies
- Change scripts to `castmasta = "castmasta.cli:main"` and `castmasta-mcp = "castmasta.mcp_server:main"`

**Step 2: Remove old package**

Run: `rm -rf airplay_agent/ airplay_agent.egg-info/`

**Step 3: Reinstall in dev mode**

Run: `.venv/bin/pip install -e ".[dev]"`

**Step 4: Run all tests**

Run: `.venv/bin/pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```
git rm -r airplay_agent/
git add pyproject.toml
git commit -m "feat: rename to castmasta, add pychromecast dep, remove old airplay_agent"
```

---

### Task 11: Update documentation and systemd

**Files:**
- Modify: `usage.md`
- Modify: `systemd/airplay-agent.service` (rename to `systemd/castmasta.service`)
- Modify: `systemd/airplay-agent@.service` (rename to `systemd/castmasta@.service`)

**Step 1: Rewrite `usage.md`**

- Title: "CastMasta"
- Description: "LLM agent for controlling AirPlay and Google Cast devices"
- All CLI examples use `castmasta` command
- Scan output shows `[airplay]` or `[googlecast]` tags
- New section: "Google Cast Notes" (power_off = quit app, no send_key, file server port 8089)
- Supported Devices: add Chromecast, Google Home, Nest Hub, etc.
- MCP tools list: add `display_image`, note `send_key` is AirPlay-only

**Step 2: Rename systemd service files**

Rename and update references from `airplay-agent`/`airplay-mcp` to `castmasta`/`castmasta-mcp`.

**Step 3: Commit**

```
git add usage.md
git rm systemd/airplay-agent.service systemd/airplay-agent@.service
git add systemd/castmasta.service systemd/castmasta@.service
git commit -m "docs: update for castmasta rename and Google Cast support"
```

---

### Task 12: Final verification

**Step 1: Run full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: All tests PASS

**Step 2: Syntax check all files**

Run: `python3 -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('castmasta/*.py')]; print('All OK')"`
Expected: All OK

**Step 3: Verify CLI help**

Run: `.venv/bin/castmasta --help`
Expected: Shows all commands

**Step 4: Verify import**

Run: `.venv/bin/python -c "from castmasta import CastAgent; print('OK')"`
Expected: OK
