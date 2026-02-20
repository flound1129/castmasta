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
