# Python API Reference

## Quick Start

```python
import asyncio
from castmasta import CastAgent, AgentConfig

async def main():
    agent = CastAgent()
    devices = await agent.scan()
    print(devices)
    # [{'name': 'Living Room TV', 'address': '192.168.1.10',
    #   'identifier': 'AA:BB:CC:DD:EE:FF', 'device_type': 'airplay', 'protocols': ['AirPlay']},
    #  {'name': 'Kitchen', 'address': '192.168.1.20',
    #   'identifier': 'uuid-1234-...', 'device_type': 'googlecast', 'protocols': ['googlecast']}]

    await agent.connect_by_name("Living Room TV")
    await agent.set_volume("AA:BB:CC:DD:EE:FF", 0.5)
    await agent.stream_file("AA:BB:CC:DD:EE:FF", "/path/to/music.mp3")
    await agent.disconnect_all()

asyncio.run(main())
```

---

## CastAgent

```python
from castmasta import CastAgent, AgentConfig

agent = CastAgent(config=AgentConfig())
```

`CastAgent` is the main entry point. All methods are `async`.

### Constructor

```python
CastAgent(config: Optional[AgentConfig] = None)
```

| Parameter | Type | Description |
|---|---|---|
| `config` | `AgentConfig` | Optional configuration. Defaults to `AgentConfig()`. |

**Instance attributes:**

| Attribute | Type | Description |
|---|---|---|
| `devices` | `dict[str, DeviceBackend]` | Currently connected devices, keyed by identifier |
| `credentials` | `CredentialStore` | Credential storage instance |
| `config` | `AgentConfig` | Active configuration |

---

### Scanning

#### `scan(timeout=5) → list[dict]`

Scans for both AirPlay and Google Cast devices concurrently.

```python
devices = await agent.scan(timeout=10)
```

Each device dict:
```python
{
    "name": "Living Room TV",
    "address": "192.168.1.10",
    "identifier": "AA:BB:CC:DD:EE:FF",   # UUID for Cast, MAC-like for AirPlay
    "device_type": "airplay",              # or "googlecast"
    "protocols": ["AirPlay", "Companion"], # or ["googlecast"]
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `timeout` | `int` | `5` | Seconds to scan. Clamped to [1, 30]. |

---

### Connecting

#### `connect_by_name(name, protocol=Protocol.AirPlay) → DeviceBackend`

Scans and connects to the first device matching `name`. Auto-detects device type.

```python
backend = await agent.connect_by_name("Kitchen Speaker")
```

Raises `ValueError` if device not found.

#### `connect(identifier, address, name, protocol=Protocol.AirPlay, device_type=None) → DeviceBackend`

Connect to a device directly when you already have its identifier and address.

```python
backend = await agent.connect(
    identifier="AA:BB:CC:DD:EE:FF",
    address="192.168.1.10",
    name="Living Room TV",
    device_type="airplay",  # optional, resolved from last scan if omitted
)
```

#### `disconnect(identifier)`

Disconnect one device and remove it from `agent.devices`.

#### `disconnect_all()`

Disconnect all connected devices.

---

### Pairing (AirPlay only)

Required for some AirPlay devices before streaming.

#### `pair(identifier, address, name, protocol=Protocol.AirPlay) → dict`

Start a pairing session. Returns a status dict.

```python
result = await agent.pair("AA:BB:CC:DD:EE:FF", "192.168.1.10", "My TV")
# {"status": "pin_required", "message": "Enter PIN on the device itself"}
# or
# {"status": "ready", "message": "PIN required - use pair_with_pin method"}
```

Raises `ValueError` for Google Cast devices (no pairing needed).

#### `pair_with_pin(identifier, address, name, pin, protocol=Protocol.AirPlay) → bool`

Complete a pairing session with the PIN shown on the device.

```python
success = await agent.pair_with_pin(
    "AA:BB:CC:DD:EE:FF", "192.168.1.10", "My TV", "1234"
)
```

Returns `True` on success. Credentials are saved to `~/.castmasta/credentials.json`.

---

### Playback

All playback methods take `identifier: str` as first argument.

#### `play(identifier)`
Resume playback.

#### `pause(identifier)`
Pause playback.

#### `stop(identifier)`
Stop playback. Also shuts down the file server if a local file was being served (Cast only).

#### `seek(identifier, position: float)`
Seek to `position` seconds.

#### `play_url(identifier, url: str, **kwargs)`

Play a URL. Validates scheme (must be `http` or `https`) and hostname.

```python
await agent.play_url("device-id", "https://example.com/video.mp4")
```

#### `stream_file(identifier, file_path: str)`

Stream a local file. Validates extension and resolves symlinks.

Allowed extensions: `.mp3 .wav .flac .ogg .mp4 .m4a .aac .m4v .mov`

```python
await agent.stream_file("device-id", "/home/user/music/song.flac")
```

Raises `FileNotFoundError` if the file doesn't exist, `ValueError` for unsupported types.

#### `display_image(identifier, image_path: str, duration: int = 3600)`

Convert an image to MP4 via ffmpeg and stream it. Requires `ffmpeg` on `PATH`.

```python
await agent.display_image("device-id", "/path/to/photo.jpg", duration=300)
```

Allowed image formats: `.png .jpg .jpeg .bmp .gif .webp`

Duration is clamped to [1, 86400] seconds.

Raises `RuntimeError` if ffmpeg fails.

#### `now_playing(identifier) → dict`

```python
info = await agent.now_playing("device-id")
# {
#     "media_type": "Music",
#     "device_state": "Playing",
#     "title": "Song Title",
#     "artist": "Artist Name",
#     "album": "Album Name",
#     "position": 45.2,
#     "total_time": 240.0,
# }
```

---

### Volume

#### `set_volume(identifier, volume: float)`
Set volume to `0.0` (mute) – `1.0` (max).

#### `volume_up(identifier, delta: float = 0.1)`
Increase volume by `delta`. Clamped to 1.0.

#### `volume_down(identifier, delta: float = 0.1)`
Decrease volume by `delta`. Clamped to 0.0.

#### `get_volume(identifier) → float`
Return current volume in [0.0, 1.0].

---

### Power

#### `power_on(identifier)`
Turn on the device. No-op on Google Cast (Cast devices are always on when reachable).

#### `power_off(identifier)`
Turn off the device. On Google Cast, this quits the active app.

#### `get_power_state(identifier) → bool`
Return `True` if on.

---

### Remote Control

#### `send_key(identifier, key: str)`

Send a remote control key press. **AirPlay only** — raises `ValueError` on Google Cast.

Valid keys: `up down left right select menu home play pause play_pause next previous`

```python
await agent.send_key("device-id", "select")
```

---

### Tool Definitions

#### `get_tool_definitions() → list[dict]`

Return LLM function-calling tool definitions (JSON schema format).

```python
tools = agent.get_tool_definitions()
```

---

## AgentConfig

```python
from castmasta import AgentConfig

config = AgentConfig(
    scan_timeout=10.0,
    storage_path="/custom/path/credentials.json",
    cast_file_server_port=8089,
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `scan_timeout` | `float` | `5.0` | Default scan timeout in seconds |
| `default_credentials` | `Optional[dict]` | `None` | Pre-seeded credentials |
| `storage_path` | `Optional[str]` | `None` | Path to credentials file. Defaults to `~/.castmasta/credentials.json` |
| `cast_file_server_port` | `int` | `8089` | HTTP port for Cast local file streaming |

---

## DeviceConfig

Represents a known device (e.g., for pre-configuring connections without scanning).

```python
from castmasta import DeviceConfig

device = DeviceConfig(
    identifier="AA:BB:CC:DD:EE:FF",
    name="Living Room TV",
    address="192.168.1.10",
    port=7000,
    protocol="airplay",
)
```

---

## CredentialStore

Low-level credential access. Usually managed transparently by `CastAgent`.

```python
from castmasta.credentials import CredentialStore

store = CredentialStore(storage_path="/path/to/creds.json")
store.set("AA:BB:CC:DD:EE:FF", "AirPlay", "<credential-string>")
cred = store.get("AA:BB:CC:DD:EE:FF", "AirPlay")
store.delete("AA:BB:CC:DD:EE:FF", "AirPlay")  # delete one protocol
store.delete("AA:BB:CC:DD:EE:FF")              # delete all protocols for device
```

---

## DeviceBackend (Advanced)

If you want to use a backend directly without `CastAgent`:

```python
from castmasta.airplay_backend import AirPlayBackend
from castmasta.cast_backend import GoogleCastBackend

# AirPlay
backend = AirPlayBackend()
await backend.connect("AA:BB:CC:DD:EE:FF", "192.168.1.10", "My TV")
await backend.play()
await backend.disconnect()

# Google Cast
backend = GoogleCastBackend(file_server_port=8089)
await backend.connect("uuid-1234", "192.168.1.20", "Kitchen")
await backend.play_url("https://example.com/video.mp4")
await backend.disconnect()
```

Both implement `DeviceBackend`. See `castmasta/backend.py` for the full interface.
