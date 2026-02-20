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
