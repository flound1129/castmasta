# CastMasta

LLM agent for controlling AirPlay and Google Cast devices (Apple TV, HomePod, Chromecast, Google Home, Nest Hub, AirPlay speakers, AV receivers).

## Installation

```bash
pip install -e .
```

## Running as a System Service

### System-wide (requires root)

```bash
sudo cp systemd/castmasta.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable castmasta
sudo systemctl start castmasta
```

### Per-user (no root required)

```bash
mkdir -p ~/.config/systemd/user
cp systemd/castmasta@.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable castmasta
systemctl --user start castmasta
```

Check status:
```bash
# System-wide
sudo systemctl status castmasta

# Per-user
systemctl --user status castmasta
```

View logs:
```bash
# System-wide
sudo journalctl -u castmasta -f

# Per-user
journalctl --user -u castmasta -f
```

## CLI Usage

### Scan for devices

```bash
castmasta scan
```

Output shows device type tags:
```
Found devices:
  - Living Room TV (192.168.1.10) [airplay]
    Identifier: XXXX-XXXX
    Protocols: AirPlay, Companion
  - Kitchen Speaker (192.168.1.20) [googlecast]
    Identifier: uuid-1234
    Protocols: googlecast
```

### Connect to a device

```bash
# Auto-detects device type (AirPlay or Google Cast)
castmasta connect "Living Room TV"
```

### Pairing (AirPlay only)

Some AirPlay devices require pairing before certain operations:

```bash
# Start pairing - will show PIN on your TV
castmasta pair "Main Bedroom"

# Complete pairing with PIN
castmasta pair-pin "Main Bedroom" 1234
```

Credentials are cached in `~/.castmasta/credentials.json`.

To remove cached credentials:
```bash
castmasta remove-credentials <device_identifier>
```

### Playback control

```bash
castmasta play <device_id>
castmasta pause <device_id>
castmasta stop <device_id>
castmasta seek <device_id> 60  # seek to 60 seconds
castmasta send-key <device_id> up  # AirPlay only
```

### Streaming

```bash
# Play a URL (video or audio)
castmasta play-url <device_id> "https://example.com/video.mp4"

# Stream a local file
castmasta stream-file <device_id> "/path/to/file.mp3"
```

Supported file formats:
- Audio: MP3, WAV, FLAC, OGG, AAC, M4A
- Video: MP4, M4V, MOV

### Display image

Display a static image on a device (requires ffmpeg). The image is converted to an MP4 video and streamed.

```bash
# Display an image for 1 hour (default)
castmasta display-image <device_id> "/path/to/image.png"

# Display for a specific duration (in seconds)
castmasta display-image <device_id> "/path/to/photo.jpg" --duration 300
```

Supported image formats: PNG, JPG, JPEG, BMP, GIF, WEBP

### Volume control

```bash
castmasta set-volume <device_id> 0.5    # 0.0 to 1.0
castmasta volume-up <device_id>
castmasta volume-down <device_id>
castmasta get-volume <device_id>
```

### Power control

```bash
castmasta power-on <device_id>    # AirPlay only; no-op on Google Cast
castmasta power-off <device_id>   # Quits app on Google Cast
castmasta power-state <device_id>
```

### Now playing

```bash
castmasta now-playing <device_id>
```

### Disconnect

```bash
castmasta disconnect <device_id>
```

## Google Cast Notes

- **Power on** is a no-op (Cast devices are always on when reachable)
- **Power off** quits the running app on the Chromecast
- **send-key** is not supported (raises an error)
- **Pairing** is not required for Google Cast devices
- Local file streaming uses an HTTP file server on port 8089 (configurable via `AgentConfig.cast_file_server_port`)

## LLM Integration

### Get tool definitions (JSON)

```bash
castmasta tools
```

This outputs JSON tool definitions compatible with LLM function calling.

## MCP Server

CastMasta can be run as an MCP (Model Context Protocol) server, compatible with Claude Desktop, Cursor, and other MCP clients.

### Running the MCP Server

```bash
# Run with stdio transport (for Claude Desktop)
python -m castmasta.mcp_server

# Or use the CLI entry point (after pip install)
castmasta-mcp
```

### Claude Desktop Configuration

Add this to your Claude Desktop config:

```json
{
  "mcpServers": {
    "castmasta": {
      "command": "castmasta-mcp"
    }
  }
}
```

### Available MCP Tools

- `scan_devices` - Scan for AirPlay and Google Cast devices
- `connect_device` - Connect to a device by name (auto-detects type)
- `disconnect_device` - Disconnect from a device
- `power_on` / `power_off` / `get_power_state` - Power control
- `play` / `pause` / `stop` / `seek` - Playback control
- `play_url` - Play a URL
- `stream_file` - Stream a local file
- `display_image` - Display a static image (converts to video via ffmpeg)
- `set_volume` / `volume_up` / `volume_down` / `get_volume` - Volume control
- `now_playing` - Get current media info
- `send_key` - Send remote control key (AirPlay only)
- `pair_device` / `pair_device_with_pin` - Device pairing (AirPlay only)

## Python API

```python
import asyncio
from castmasta import CastAgent

async def main():
    agent = CastAgent()

    # Scan for devices (both AirPlay and Google Cast)
    devices = await agent.scan()
    print(devices)

    # Connect (auto-detects device type)
    await agent.connect_by_name("Living Room TV")

    # Control
    await agent.play_url("device-id", "https://example.com/video.mp4")
    await agent.set_volume("device-id", 0.5)

    # Get now playing
    info = await agent.now_playing("device-id")
    print(info)

    await agent.disconnect_all()

asyncio.run(main())
```

## Supported Devices

### AirPlay
- Apple TV (all generations)
- HomePod / HomePod mini
- AirPort Express
- AirPlay-enabled receivers (Onkyo, Denon, etc.)
- Macs (as AirPlay targets)
- Roku (AirPlay-enabled)

### Google Cast
- Chromecast (all generations)
- Chromecast with Google TV
- Google Home / Home Mini / Home Max
- Google Nest Hub / Nest Hub Max
- Nest Audio
- Cast-enabled speakers and displays
