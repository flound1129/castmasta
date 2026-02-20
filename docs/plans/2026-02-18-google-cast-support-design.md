# Google Cast Support Design

## Summary

Add Google Cast (Chromecast) support to the agent alongside existing AirPlay support. Rename the package from `airplay_agent` to `castmasta` (CLI: `castmasta`, MCP: `castmasta-mcp`). Unified interface — one set of commands works for both AirPlay and Google Cast devices.

## Architecture: Protocol Backend Pattern

Introduce a `DeviceBackend` ABC with two implementations. The main `CastAgent` dispatches to the correct backend by device identifier.

### File Layout

```
castmasta/
  __init__.py          # exports CastAgent, AgentConfig
  agent.py             # CastAgent — unified facade
  backend.py           # DeviceBackend ABC
  airplay_backend.py   # AirPlayBackend (wraps pyatv)
  cast_backend.py      # GoogleCastBackend (wraps pychromecast)
  config.py            # AgentConfig, DeviceConfig
  credentials.py       # CredentialStore (extracted from current agent.py)
  file_server.py       # HTTP file server for Cast local file streaming
  cli.py               # click CLI
  mcp_server.py        # MCP tools
  tools.py             # LLM tool definitions
```

### DeviceBackend ABC

Each backend instance represents one connected device. Methods:

- `connect(identifier, address, name, **kwargs)`
- `disconnect()`
- `stream_file(file_path)` / `play_url(url, **kwargs)`
- `play()` / `pause()` / `stop()` / `seek(position)`
- `set_volume(volume)` / `get_volume()`
- `now_playing()` → dict
- `power_on()` / `power_off()` / `get_power_state()`

### CastAgent (Unified Facade)

- **Scanning:** Runs `pyatv.scan()` and `pychromecast.get_chromecasts()` concurrently. Returns unified list with `device_type` field ("airplay" or "googlecast"). Cast devices use UUID as identifier.
- **Connecting:** `connect()` uses cached scan results to determine backend type. `connect_by_name()` scans and resolves automatically.
- **Validation:** File/URL/volume/duration validation stays in the agent (shared). Backends do protocol-specific work only.
- **Credentials:** AirPlay-only (PIN pairing). `pair`/`pair_with_pin` raise `ValueError` for Cast.
- **display_image:** Agent-level — ffmpeg conversion then `backend.stream_file()`.
- **send_key:** AirPlay-only. Raises `ValueError` for Cast.
- **volume_up/volume_down:** Agent-level, composed from `get_volume` + `set_volume`.

## GoogleCastBackend Details

**Library:** `pychromecast>=14.0.0`

### Method Mapping

| Agent method | PyChromecast equivalent |
|---|---|
| stream_file | HTTP server + `mc.play_media(url, content_type)` |
| play_url | `mc.play_media(url, content_type)` |
| play/pause/stop | `mc.play()` / `mc.pause()` / `mc.stop()` |
| seek | `mc.seek(position)` |
| set_volume | `cast.set_volume(volume)` |
| get_volume | `cast.status.volume_level` |
| now_playing | `mc.status` fields |
| power_on | No-op (device always on when reachable) |
| power_off | `cast.quit_app()` |
| get_power_state | `cast.status is not None` |

### Local File HTTP Server

Cast devices can't play local files directly — they need an HTTP URL. The backend runs a lightweight `aiohttp` server to serve the file.

- **Bind:** `0.0.0.0` (must be reachable from Chromecast on LAN)
- **Port:** Fixed default `8089`, configurable via `AgentConfig.cast_file_server_port`
- **Lifecycle:** Server starts when streaming begins, background task monitors media controller status, shuts down when playback ends or device disconnects
- **Security:** Serves only the single requested file per session

### Async Threading

PyChromecast uses threads internally. All blocking calls wrapped with `asyncio.to_thread()`.

## Error Handling

- **Unsupported operations:** `ValueError` with clear message (e.g., "send_key is not supported on Google Cast devices")
- **Power control on Cast:** `power_on` is no-op, `power_off` quits app, `get_power_state` checks reachability

## Dependencies

Add to `pyproject.toml`:
- `pychromecast>=14.0.0`
