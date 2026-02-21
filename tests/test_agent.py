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
import os
from pathlib import Path
import asyncio


@pytest.mark.asyncio
async def test_announce_streams_wav(agent, mock_airplay_backend, tmp_path):
    """announce() runs piper and calls stream_file with a .wav path."""
    agent.devices["dev1"] = mock_airplay_backend

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(None, b""))

    with patch("castmasta.agent.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await agent.announce("dev1", "Hello world")

    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert call_args[0] == "piper"
    assert "--output_file" in call_args
    output_path = call_args[call_args.index("--output_file") + 1]
    assert output_path.endswith(".wav")

    mock_airplay_backend.stream_file.assert_called_once()
    streamed_path = mock_airplay_backend.stream_file.call_args[0][0]
    assert streamed_path.endswith(".wav")


@pytest.mark.asyncio
async def test_announce_cleans_up_temp_file_on_success(agent, mock_airplay_backend):
    """Temp WAV file is deleted after streaming."""
    agent.devices["dev1"] = mock_airplay_backend

    captured_path = []

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(None, b""))

    async def fake_exec(*args, **kwargs):
        output_path = args[args.index("--output_file") + 1]
        captured_path.append(output_path)
        Path(output_path).write_bytes(b"fake wav")
        return mock_proc

    with patch("castmasta.agent.asyncio.create_subprocess_exec", side_effect=fake_exec):
        await agent.announce("dev1", "Hello")

    assert captured_path, "No temp file path captured"
    assert not Path(captured_path[0]).exists(), "Temp file was not cleaned up"


@pytest.mark.asyncio
async def test_announce_raises_on_empty_text(agent, mock_airplay_backend):
    agent.devices["dev1"] = mock_airplay_backend
    with pytest.raises(ValueError, match="non-empty"):
        await agent.announce("dev1", "")


@pytest.mark.asyncio
async def test_announce_raises_on_invalid_voice(agent, mock_airplay_backend):
    agent.devices["dev1"] = mock_airplay_backend
    with pytest.raises(ValueError, match="voice"):
        await agent.announce("dev1", "Hello", voice="../evil/path")


@pytest.mark.asyncio
async def test_announce_raises_on_piper_failure(agent, mock_airplay_backend):
    agent.devices["dev1"] = mock_airplay_backend

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(None, b"model not found"))

    with patch("castmasta.agent.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="piper"):
            await agent.announce("dev1", "Hello")


@pytest.mark.asyncio
async def test_announce_cleans_up_on_failure(agent, mock_airplay_backend):
    """Temp WAV file is deleted even if piper fails."""
    agent.devices["dev1"] = mock_airplay_backend

    captured_path = []

    async def fake_exec(*args, **kwargs):
        output_path = args[args.index("--output_file") + 1]
        captured_path.append(output_path)
        Path(output_path).write_bytes(b"partial")
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(None, b"error"))
        return mock_proc

    with patch("castmasta.agent.asyncio.create_subprocess_exec", side_effect=fake_exec):
        with pytest.raises(RuntimeError):
            await agent.announce("dev1", "Hello")

    if captured_path:
        assert not Path(captured_path[0]).exists(), "Temp file not cleaned up on failure"
