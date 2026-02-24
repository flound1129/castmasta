"""MCP server for CastMasta."""
import logging
from typing import Optional

import click

from fastmcp import FastMCP

from castmasta import CastAgent
from pyatv.const import Protocol

logger = logging.getLogger(__name__)

mcp = FastMCP("CastMasta")

agent: CastAgent = CastAgent()


def _parse_protocol(protocol: str) -> Optional[Protocol]:
    """Parse and validate protocol string. Returns None if invalid."""
    if protocol == "airplay":
        return Protocol.AirPlay
    elif protocol == "companion":
        return Protocol.Companion
    return None


@mcp.tool()
async def scan_devices(timeout: int = 5) -> str:
    """Scan the local network for AirPlay and Google Cast devices.

    Returns a list of all discovered devices with their names, addresses, and supported protocols.
    """
    devices = await agent.scan(timeout)
    if not devices:
        return "No devices found on the network."

    result = ["Found devices:\n"]
    for dev in devices:
        result.append(f"- {dev['name']} ({dev['address']}) [{dev['device_type']}]")
        result.append(f"  Identifier: {dev['identifier']}")
        result.append(f"  Protocols: {', '.join(dev['protocols'])}")
    return "\n".join(result)


@mcp.tool()
async def connect_device(name: str, protocol: str = "airplay", host: Optional[str] = None) -> str:
    """Connect to a device by name (auto-detects AirPlay or Google Cast).

    Args:
        name: The name of the device to connect to
        protocol: The protocol to use - 'airplay' or 'companion' (default: airplay)
        host: Optional IP address of the device (bypasses mDNS scan)
    """
    proto = _parse_protocol(protocol)
    if proto is None:
        return f"Invalid protocol '{protocol}'. Must be 'airplay' or 'companion'."
    try:
        hosts = [host] if host else None
        identifier, backend = await agent.connect_by_name(name, proto, hosts=hosts)
        return f"Connected to {name} [{backend.device_type}] identifier={identifier}"
    except Exception:
        logger.exception("Failed to connect to device")
        return f"Failed to connect to {name}: device unreachable or pairing required"


@mcp.tool()
async def disconnect_device(identifier: str) -> str:
    """Disconnect from a device.

    Args:
        identifier: The device identifier
    """
    try:
        await agent.disconnect(identifier)
        return f"Disconnected from {identifier}"
    except Exception:
        logger.exception("Failed to disconnect")
        return f"Failed to disconnect from {identifier}"


@mcp.tool()
async def power_on(identifier: str) -> str:
    """Turn on a device (AirPlay only; no-op on Google Cast).

    Args:
        identifier: The device identifier
    """
    try:
        await agent.power_on(identifier)
        return f"Powered on {identifier}"
    except Exception:
        logger.exception("Failed to power on device")
        return f"Failed to power on {identifier}"


@mcp.tool()
async def power_off(identifier: str) -> str:
    """Turn off a device (quits app on Google Cast).

    Args:
        identifier: The device identifier
    """
    try:
        await agent.power_off(identifier)
        return f"Powered off {identifier}"
    except Exception:
        logger.exception("Failed to power off device")
        return f"Failed to power off {identifier}"


@mcp.tool()
async def get_power_state(identifier: str) -> str:
    """Get the power state of a device.

    Args:
        identifier: The device identifier
    """
    try:
        state = await agent.get_power_state(identifier)
        return f"Power state: {'on' if state else 'off'}"
    except Exception:
        logger.exception("Failed to get power state")
        return f"Failed to get power state for {identifier}"


@mcp.tool()
async def play(identifier: str) -> str:
    """Start or resume playback on a device.

    Args:
        identifier: The device identifier
    """
    try:
        await agent.play(identifier)
        return "Playing"
    except Exception:
        logger.exception("Failed to play")
        return "Failed to start playback"


@mcp.tool()
async def pause(identifier: str) -> str:
    """Pause playback on a device.

    Args:
        identifier: The device identifier
    """
    try:
        await agent.pause(identifier)
        return "Paused"
    except Exception:
        logger.exception("Failed to pause")
        return "Failed to pause playback"


@mcp.tool()
async def stop(identifier: str) -> str:
    """Stop playback on a device.

    Args:
        identifier: The device identifier
    """
    try:
        await agent.stop(identifier)
        return "Stopped"
    except Exception:
        logger.exception("Failed to stop")
        return "Failed to stop playback"


@mcp.tool()
async def play_url(identifier: str, url: str, position: float = 0) -> str:
    """Play a video or audio URL on a device.

    Args:
        identifier: The device identifier
        url: The URL to play (must be HTTP or HTTPS)
        position: Optional starting position in seconds
    """
    try:
        kwargs = {}
        if position > 0:
            kwargs["position"] = position
        await agent.play_url(identifier, url, **kwargs)
        return f"Playing URL on {identifier}"
    except ValueError as e:
        return f"Invalid URL: {e}"
    except Exception:
        logger.exception("Failed to play URL")
        return f"Failed to play URL on {identifier}"


@mcp.tool()
async def stream_file(identifier: str, file_path: str) -> str:
    """Stream a local audio/video file to a device.

    Args:
        identifier: The device identifier
        file_path: Path to local media file (MP3, WAV, FLAC, OGG, MP4, M4A, AAC)
    """
    try:
        await agent.stream_file(identifier, file_path)
        return f"Streaming file on {identifier}"
    except (ValueError, FileNotFoundError) as e:
        return f"Invalid file: {e}"
    except Exception:
        logger.exception("Failed to stream file")
        return f"Failed to stream file on {identifier}"


@mcp.tool()
async def display_image(identifier: str, image_path: str, duration: int = 3600) -> str:
    """Display a static image on a device.

    Converts the image to a video using ffmpeg and streams it to the device.

    Args:
        identifier: The device identifier
        image_path: Path to image file (PNG, JPG, JPEG, BMP, GIF, WEBP)
        duration: How long to display in seconds (default: 3600, max: 86400)
    """
    try:
        await agent.display_image(identifier, image_path, duration)
        return f"Displaying image on {identifier} for {duration}s"
    except (ValueError, FileNotFoundError) as e:
        return f"Invalid image: {e}"
    except RuntimeError as e:
        return f"ffmpeg error: {e}"
    except Exception:
        logger.exception("Failed to display image")
        return f"Failed to display image on {identifier}"


@mcp.tool()
async def announce(identifier: str, text: str, voice: str = "en_US-lessac-medium") -> str:
    """Synthesise text to speech and play it on a device.

    Uses Piper TTS to convert text to a WAV file and streams it to the device.
    Voice models must be pre-installed in ~/.local/share/piper-voices/.

    Args:
        identifier: The device identifier
        text: Text to speak (max 4000 characters)
        voice: Piper voice model name (default: en_US-lessac-medium)
    """
    try:
        await agent.announce(identifier, text, voice)
        return f"Announced on {identifier}: {text[:60]}{'...' if len(text) > 60 else ''}"
    except (ValueError, FileNotFoundError) as e:
        return f"Invalid input: {e}"
    except RuntimeError as e:
        return f"Piper TTS error: {e}"
    except Exception:
        logger.exception("Failed to announce")
        return f"Failed to announce on {identifier}"


@mcp.tool()
async def set_volume(identifier: str, volume: float) -> str:
    """Set the volume on a device.

    Args:
        identifier: The device identifier
        volume: Volume level from 0.0 (mute) to 1.0 (max)
    """
    try:
        await agent.set_volume(identifier, volume)
        return f"Volume set to {volume}"
    except ValueError as e:
        return str(e)
    except Exception:
        logger.exception("Failed to set volume")
        return f"Failed to set volume on {identifier}"


@mcp.tool()
async def volume_up(identifier: str, delta: float = 0.1) -> str:
    """Increase the volume on a device.

    Args:
        identifier: The device identifier
        delta: Amount to increase (0.0 to 1.0, default: 0.1)
    """
    try:
        await agent.volume_up(identifier, delta)
        return f"Volume up by {delta}"
    except ValueError as e:
        return str(e)
    except Exception:
        logger.exception("Failed to increase volume")
        return f"Failed to increase volume on {identifier}"


@mcp.tool()
async def volume_down(identifier: str, delta: float = 0.1) -> str:
    """Decrease the volume on a device.

    Args:
        identifier: The device identifier
        delta: Amount to decrease (0.0 to 1.0, default: 0.1)
    """
    try:
        await agent.volume_down(identifier, delta)
        return f"Volume down by {delta}"
    except ValueError as e:
        return str(e)
    except Exception:
        logger.exception("Failed to decrease volume")
        return f"Failed to decrease volume on {identifier}"


@mcp.tool()
async def get_volume(identifier: str) -> str:
    """Get the current volume level of a device.

    Args:
        identifier: The device identifier
    """
    try:
        volume = await agent.get_volume(identifier)
        return f"Volume: {volume}"
    except Exception:
        logger.exception("Failed to get volume")
        return f"Failed to get volume for {identifier}"


@mcp.tool()
async def now_playing(identifier: str) -> str:
    """Get information about currently playing media.

    Args:
        identifier: The device identifier
    """
    try:
        info = await agent.now_playing(identifier)
        return (
            f"Title: {info.get('title', 'Unknown')}\n"
            f"Artist: {info.get('artist', 'Unknown')}\n"
            f"Album: {info.get('album', 'Unknown')}\n"
            f"State: {info.get('device_state', 'Unknown')}\n"
            f"Position: {info.get('position', 0)}s / {info.get('total_time', 0)}s"
        )
    except Exception:
        logger.exception("Failed to get now playing info")
        return f"Failed to get now playing info for {identifier}"


@mcp.tool()
async def seek(identifier: str, position: float) -> str:
    """Seek to a specific position in the current media.

    Args:
        identifier: The device identifier
        position: Position in seconds
    """
    try:
        await agent.seek(identifier, position)
        return f"Seeked to {position}s"
    except Exception:
        logger.exception("Failed to seek")
        return f"Failed to seek on {identifier}"


@mcp.tool()
async def send_key(identifier: str, key: str) -> str:
    """Send a remote control key press (AirPlay only).

    Args:
        identifier: The device identifier
        key: Key name - up, down, left, right, select, menu, home, play, pause, play_pause, next, previous
    """
    try:
        await agent.send_key(identifier, key)
        return f"Sent key: {key}"
    except ValueError as e:
        return str(e)
    except Exception:
        logger.exception("Failed to send key")
        return f"Failed to send key on {identifier}"


@mcp.tool()
async def pair_device(name: str, protocol: str = "airplay", host: Optional[str] = None) -> str:
    """Start pairing with a device (AirPlay only).

    Args:
        name: The name of the device to pair with
        protocol: The protocol - 'airplay' or 'companion'
        host: Optional IP address of the device (bypasses mDNS scan)
    """
    proto = _parse_protocol(protocol)
    if proto is None:
        return f"Invalid protocol '{protocol}'. Must be 'airplay' or 'companion'."
    try:
        hosts = [host] if host else None
        devices = await agent.scan(hosts=hosts)
        for dev in devices:
            if dev["name"] == name:
                result = await agent.pair(dev["identifier"], dev["address"], dev["name"], proto)
                return f"Pairing initiated for {name}. Status: {result['status']}. Use pair_device_with_pin to complete."
        return f"Device '{name}' not found"
    except ValueError as e:
        return str(e)
    except Exception:
        logger.exception("Failed to start pairing")
        return f"Failed to pair with {name}"


@mcp.tool()
async def pair_device_with_pin(name: str, pin: str, protocol: str = "airplay", host: Optional[str] = None) -> str:
    """Complete pairing with a PIN code (AirPlay only).

    Args:
        name: The name of the device to pair with
        pin: The PIN code (4 digits)
        protocol: The protocol - 'airplay' or 'companion'
        host: Optional IP address of the device (bypasses mDNS scan)
    """
    proto = _parse_protocol(protocol)
    if proto is None:
        return f"Invalid protocol '{protocol}'. Must be 'airplay' or 'companion'."
    try:
        hosts = [host] if host else None
        devices = await agent.scan(hosts=hosts)
        for dev in devices:
            if dev["name"] == name:
                success = await agent.pair_with_pin(dev["identifier"], dev["address"], dev["name"], pin, proto)
                if success:
                    return "Pairing successful! Credentials cached."
                return "Pairing failed. Please try again."
        return f"Device '{name}' not found"
    except ValueError as e:
        return str(e)
    except Exception:
        logger.exception("Failed to complete pairing")
        return f"Failed to complete pairing with {name}"


@click.command()
@click.option("--host", default="127.0.0.1", help="Host to listen on")
@click.option("--port", default=16384, help="Port to listen on")
@click.option("--stdio", "transport", flag_value="stdio", default=True, help="Use stdio transport (default)")
@click.option("--http", "transport", flag_value="http", help="Use HTTP transport")
def main(host, port, transport):
    if transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
