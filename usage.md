# AirPlay Agent

LLM agent for controlling AirPlay devices (Apple TV, HomePod, AirPlay speakers, AV receivers).

## Installation

```bash
pip install -e .
```

## CLI Usage

### Scan for devices

```bash
python -m airplay_agent.cli scan
# or after pip install:
airplay-agent scan
```

### Connect to a device

```bash
python -m airplay_agent.cli connect "Main Bedroom"
```

### Pairing (for devices that require PIN)

Some devices (like Apple TV, Roku) require pairing before certain operations:

```bash
# Start pairing - will show PIN on your TV
python -m airplay_agent.cli pair "Main Bedroom"

# Complete pairing with PIN
python -m airplay_agent.cli pair-pin "Main Bedroom" 1234
```

Credentials are cached in `~/.airplay-agent/credentials.json`.

To remove cached credentials:
```bash
python -m airplay_agent.cli remove-credentials <device_identifier>
```

### Playback control

```bash
python -m airplay_agent.cli play <device_id>
python -m airplay_agent.cli pause <device_id>
python -m airplay_agent.cli stop <device_id>
python -m airplay_agent.cli seek <device_id> 60  # seek to 60 seconds
python -m airplay_agent.cli send-key <device_id> up  # send remote key
```

### Streaming

```bash
# Play a URL (video or audio)
python -m airplay_agent.cli play-url <device_id> "https://example.com/video.mp4"

# Stream a local file
python -m airplay_agent.cli stream-file <device_id> "/path/to/file.mp3"
```

Supported file formats:
- Audio: MP3, WAV, FLAC, OGG
- Video: MP4 (must be AirPlay-compatible)

### Volume control

```bash
python -m airplay_agent.cli set-volume <device_id> 0.5    # 0.0 to 1.0
python -m airplay_agent.cli volume-up <device_id>
python -m airplay_agent.cli volume-down <device_id>
python -m airplay_agent.cli get-volume <device_id>
```

### Power control

```bash
python -m airplay_agent.cli power-on <device_id>
python -m airplay_agent.cli power-off <device_id>
python -m airplay_agent.cli power-state <device_id>
```

### Now playing

```bash
python -m airplay_agent.cli now-playing <device_id>
```

### Disconnect

```bash
python -m airplay_agent.cli disconnect <device_id>
```

## LLM Integration

### Get tool definitions (JSON)

```bash
python -m airplay_agent.cli tools
```

This outputs JSON tool definitions compatible with Ollama's function calling.

### Ollama Integration

1. Start Ollama with a model that supports tools:
   ```bash
   ollama run qwen2.5-coder
   ```

2. Use the tool definitions from `tools` output to enable function calling.

### OpenCode Integration

The project includes `opencode.json` configured for Ollama at `localhost:11434`:

```bash
opencode
```

## MCP Server

The AirPlay agent can be run as an MCP (Model Context Protocol) server, making it compatible with Claude Desktop, Cursor, and other MCP clients.

### Installation

```bash
pip install -e ".[mcp]"
# or just:
pip install fastmcp
```

### Running the MCP Server

```bash
# Run with stdio transport (for Claude Desktop)
python -m airplay_agent.mcp_server

# Or use the CLI entry point (after pip install)
airplay-mcp
```

### Claude Desktop Configuration

Add this to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "airplay-agent": {
      "command": "python",
      "args": ["-m", "airplay_agent.mcp_server"],
      "env": {
        "PATH": "/path/to/your/venv/bin"
      }
    }
  }
}
```

Or if installed globally:

```json
{
  "mcpServers": {
    "airplay-agent": {
      "command": "airplay-mcp"
    }
  }
}
```

### Available MCP Tools

The MCP server exposes these tools:
- `scan_devices` - Scan for AirPlay devices
- `connect_device` - Connect to a device by name
- `disconnect_device` - Disconnect from a device
- `power_on` / `power_off` / `get_power_state` - Power control
- `play` / `pause` / `stop` / `seek` - Playback control
- `play_url` - Play a URL
- `stream_file` - Stream a local file
- `set_volume` / `volume_up` / `volume_down` / `get_volume` - Volume control
- `now_playing` - Get current media info
- `send_key` - Send remote control key
- `pair_device` / `pair_device_with_pin` - Device pairing

## Python API

```python
import asyncio
from airplay_agent import AirPlayAgent

async def main():
    agent = AirPlayAgent()
    
    # Scan for devices
    devices = await agent.scan()
    print(devices)
    
    # Connect
    await agent.connect_by_name("Main Bedroom")
    
    # Control
    await agent.play_url("main-bedroom", "https://example.com/video.mp4")
    await agent.set_volume("main-bedroom", 0.5)
    
    # Get now playing
    info = await agent.now_playing("main-bedroom")
    print(info)
    
    await agent.disconnect_all()

asyncio.run(main())
```

## Supported Devices

- Apple TV (all generations)
- HomePod / HomePod mini
- AirPort Express
- AirPlay-enabled receivers (Onkyo, Denon, etc.)
- Macs (as AirPlay targets)
- Roku (AirPlay-enabled)
