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
