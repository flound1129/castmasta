"""MCP server for AirPlay agent."""
import asyncio
from typing import Optional

from fastmcp import FastMCP

from airplay_agent import AirPlayAgent
from pyatv.const import Protocol

mcp = FastMCP("AirPlay Agent")

agent: Optional[AirPlayAgent] = None


def get_agent() -> AirPlayAgent:
    global agent
    if agent is None:
        agent = AirPlayAgent()
    return agent


@mcp.tool()
async def scan_devices(timeout: int = 5) -> str:
    """Scan the local network for AirPlay devices.
    
    Returns a list of all discovered devices with their names, addresses, and supported protocols.
    """
    a = get_agent()
    devices = await a.scan(timeout)
    if not devices:
        return "No devices found on the network."
    
    result = ["Found devices:\n"]
    for dev in devices:
        result.append(f"- {dev['name']} ({dev['address']})")
        result.append(f"  Identifier: {dev['identifier']}")
        result.append(f"  Protocols: {', '.join(dev['protocols'])}")
    return "\n".join(result)


@mcp.tool()
async def connect_device(name: str, protocol: str = "airplay") -> str:
    """Connect to an AirPlay device by name.
    
    Args:
        name: The name of the device to connect to (e.g., 'Main Bedroom')
        protocol: The protocol to use - 'airplay' or 'companion' (default: airplay)
    """
    a = get_agent()
    proto = Protocol.AirPlay if protocol == "airplay" else Protocol.Companion
    try:
        atv = await a.connect_by_name(name, proto)
        return f"Connected to {name}"
    except Exception as e:
        return f"Failed to connect to {name}: {str(e)}"


@mcp.tool()
async def disconnect_device(identifier: str) -> str:
    """Disconnect from an AirPlay device.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        await a.disconnect(identifier)
        return f"Disconnected from {identifier}"
    except Exception as e:
        return f"Failed to disconnect: {str(e)}"


@mcp.tool()
async def power_on(identifier: str) -> str:
    """Turn on an AirPlay device.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        await a.power_on(identifier)
        return f"Powered on {identifier}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def power_off(identifier: str) -> str:
    """Turn off an AirPlay device.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        await a.power_off(identifier)
        return f"Powered off {identifier}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def get_power_state(identifier: str) -> str:
    """Get the power state of a device.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        state = await a.get_power_state(identifier)
        return f"Power state: {'on' if state else 'off'}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def play(identifier: str) -> str:
    """Start or resume playback on a device.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        await a.play(identifier)
        return "Playing"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def pause(identifier: str) -> str:
    """Pause playback on a device.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        await a.pause(identifier)
        return "Paused"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def stop(identifier: str) -> str:
    """Stop playback on a device.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        await a.stop(identifier)
        return "Stopped"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def play_url(identifier: str, url: str, position: float = 0) -> str:
    """Play a video or audio URL on a device.
    
    Args:
        identifier: The device identifier
        url: The URL to play (can be HTTP/HTTPS)
        position: Optional starting position in seconds
    """
    a = get_agent()
    try:
        kwargs = {}
        if position > 0:
            kwargs["position"] = position
        await a.play_url(identifier, url, **kwargs)
        return f"Playing {url}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def stream_file(identifier: str, file_path: str) -> str:
    """Stream a local audio/video file to a device.
    
    Args:
        identifier: The device identifier
        file_path: Path to local file (MP3, WAV, FLAC, OGG, MP4)
    """
    a = get_agent()
    try:
        await a.stream_file(identifier, file_path)
        return f"Streaming {file_path}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def set_volume(identifier: str, volume: float) -> str:
    """Set the volume on a device.
    
    Args:
        identifier: The device identifier
        volume: Volume level from 0.0 (mute) to 1.0 (max)
    """
    a = get_agent()
    try:
        await a.set_volume(identifier, volume)
        return f"Volume set to {volume}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def volume_up(identifier: str, delta: float = 0.1) -> str:
    """Increase the volume on a device.
    
    Args:
        identifier: The device identifier
        delta: Amount to increase (default: 0.1)
    """
    a = get_agent()
    try:
        await a.volume_up(identifier, delta)
        return f"Volume up by {delta}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def volume_down(identifier: str, delta: float = 0.1) -> str:
    """Decrease the volume on a device.
    
    Args:
        identifier: The device identifier
        delta: Amount to decrease (default: 0.1)
    """
    a = get_agent()
    try:
        await a.volume_down(identifier, delta)
        return f"Volume down by {delta}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def get_volume(identifier: str) -> str:
    """Get the current volume level of a device.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        volume = await a.get_volume(identifier)
        return f"Volume: {volume}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def now_playing(identifier: str) -> str:
    """Get information about currently playing media.
    
    Args:
        identifier: The device identifier
    """
    a = get_agent()
    try:
        info = await a.now_playing(identifier)
        return (
            f"Title: {info.get('title', 'Unknown')}\n"
            f"Artist: {info.get('artist', 'Unknown')}\n"
            f"Album: {info.get('album', 'Unknown')}\n"
            f"State: {info.get('device_state', 'Unknown')}\n"
            f"Position: {info.get('position', 0)}s / {info.get('total_time', 0)}s"
        )
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def seek(identifier: str, position: float) -> str:
    """Seek to a specific position in the current media.
    
    Args:
        identifier: The device identifier
        position: Position in seconds
    """
    a = get_agent()
    try:
        await a.seek(identifier, position)
        return f"Seeked to {position}s"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def send_key(identifier: str, key: str) -> str:
    """Send a remote control key press.
    
    Args:
        identifier: The device identifier
        key: Key name - up, down, left, right, select, menu, home, play, pause, play_pause, next, previous
    """
    a = get_agent()
    try:
        await a.send_key(identifier, key)
        return f"Sent key: {key}"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def pair_device(name: str, protocol: str = "airplay") -> str:
    """Start pairing with a device (for devices that require PIN).
    
    Args:
        name: The name of the device to pair with
        protocol: The protocol - 'airplay' or 'companion'
    """
    a = get_agent()
    try:
        devices = await a.scan()
        for dev in devices:
            if dev["name"] == name:
                proto = Protocol.AirPlay if protocol == "airplay" else Protocol.Companion
                result = await a.pair(dev["identifier"], dev["address"], dev["name"], proto)
                return f"Pairing initiated for {name}. Use pair_device_with_pin to complete."
        return f"Device '{name}' not found"
    except Exception as e:
        return f"Failed: {str(e)}"


@mcp.tool()
async def pair_device_with_pin(name: str, pin: str, protocol: str = "airplay") -> str:
    """Complete pairing with a PIN code.
    
    Args:
        name: The name of the device to pair with
        pin: The PIN code (4 digits)
        protocol: The protocol - 'airplay' or 'companion'
    """
    a = get_agent()
    try:
        devices = await a.scan()
        for dev in devices:
            if dev["name"] == name:
                proto = Protocol.AirPlay if protocol == "airplay" else Protocol.Companion
                success = await a.pair_with_pin(dev["identifier"], dev["address"], dev["name"], pin, proto)
                if success:
                    return "Pairing successful! Credentials cached."
                return "Pairing failed. Please try again."
        return f"Device '{name}' not found"
    except Exception as e:
        return f"Failed: {str(e)}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        mcp.run()
    else:
        mcp.run(transport="stdio")
