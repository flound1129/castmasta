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
