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
