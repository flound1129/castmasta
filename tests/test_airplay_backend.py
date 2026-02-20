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
    atv.audio = AsyncMock()
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
    assert backend._atv is None


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
