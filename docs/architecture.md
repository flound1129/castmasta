# CastMasta Architecture

## Overview

CastMasta follows a **Protocol Backend Pattern**: a single `CastAgent` facade dispatches to protocol-specific backends (`AirPlayBackend`, `GoogleCastBackend`) based on a device's identifier. The public API is identical regardless of whether you're talking to an Apple TV or a Chromecast.

```
┌─────────────────────────────────────────────────────┐
│                   Entry Points                       │
│  CLI (castmasta)   MCP Server (castmasta-mcp)        │
│  Python API (castmasta.CastAgent)                    │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                   CastAgent                          │
│  • scan()  connect()  disconnect()                   │
│  • play/pause/stop/seek  set_volume/get_volume       │
│  • stream_file  play_url  display_image              │
│  • pair/pair_with_pin  send_key  now_playing         │
│  • Input validation, credential management           │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
┌──────────▼──────────┐   ┌──────────▼──────────────┐
│   AirPlayBackend    │   │   GoogleCastBackend      │
│   (pyatv)           │   │   (pychromecast)         │
│                     │   │                          │
│   Native async      │   │   asyncio.to_thread()    │
│                     │   │   + FileServer for       │
│                     │   │   local files            │
└─────────────────────┘   └──────────────────────────┘
           │                          │
    Apple TV / HomePod /     Chromecast / Google Home /
    AirPlay speakers          Nest Hub / Cast speakers
```

## Module Map

| Module | Responsibility |
|---|---|
| `castmasta/agent.py` | `CastAgent` — unified facade, validation, display_image |
| `castmasta/backend.py` | `DeviceBackend` ABC — 14-method contract |
| `castmasta/airplay_backend.py` | `AirPlayBackend` — pyatv wrapper |
| `castmasta/cast_backend.py` | `GoogleCastBackend` — pychromecast wrapper |
| `castmasta/file_server.py` | `FileServer` — aiohttp HTTP server for Cast local streaming |
| `castmasta/credentials.py` | `CredentialStore` — encrypted-at-rest credential JSON |
| `castmasta/config.py` | `AgentConfig`, `DeviceConfig` dataclasses |
| `castmasta/cli.py` | Click CLI entry point |
| `castmasta/mcp_server.py` | FastMCP server (stdio transport) |
| `castmasta/tools.py` | LLM tool definitions (JSON schema) |

## Key Design Decisions

### 1. DeviceBackend ABC

All device interaction goes through the `DeviceBackend` interface. This means:
- `CastAgent` never imports pyatv or pychromecast directly for playback
- Adding a new protocol (e.g., DLNA) requires only a new backend class
- Tests mock `DeviceBackend` without touching real hardware

### 2. asyncio.to_thread() for pychromecast

pychromecast is a synchronous library. Rather than forking it or wrapping it in an event loop, `GoogleCastBackend` offloads every blocking call with `asyncio.to_thread()`. This keeps the async contract consistent across both backends.

### 3. Fixed-port HTTP file server (port 8089)

Google Cast devices cannot read local files — they need a URL. `FileServer` binds an aiohttp server to `0.0.0.0:8089` (configurable via `AgentConfig.cast_file_server_port`) and serves a single file at a time. A fixed port was chosen over a random one to avoid Linux `nf-conntrack` table exhaustion in environments with many streaming operations.

### 4. Scan caches device type

`CastAgent._last_scan` stores the most recent scan results. When `connect()` is called with an identifier but no `device_type`, it resolves the type from the cache. If not found, it defaults to `"airplay"` for backwards compatibility.

### 5. Credential storage

Credentials are stored in `~/.castmasta/credentials.json` with:
- Directory permissions: `0o700`
- File permissions: `0o600`
- Atomic writes via `tempfile.mkstemp` + `os.replace`

Keys are `"{identifier}:{protocol}"` (e.g., `"AA:BB:CC:DD:EE:FF:AirPlay"`).

### 6. display_image via ffmpeg

Images are converted to a looping H.264 MP4 using `asyncio.create_subprocess_exec` (no shell, no injection risk). The temp file is created with `0o600` permissions and deleted in a `finally` block regardless of success or failure.

## Data Flow: Streaming a Local File

```
castmasta stream-file <id> /path/to/file.mp4
  │
  ▼
CastAgent.stream_file()
  ├─ _validate_media_file()   # extension check, symlink check, file exists
  ├─ _get_backend(id)
  │
  ▼ (AirPlay)                        ▼ (Google Cast)
AirPlayBackend.stream_file()    GoogleCastBackend.stream_file()
  │                               ├─ FileServer.serve_file()
  │                               │    └─ aiohttp on 0.0.0.0:8089
  │                               ├─ mc.play_media(url, content_type)
  ▼                               └─ mc.block_until_active()
atv.stream.stream_file(path)
```

## Data Flow: Scanning

```
CastAgent.scan()
  │
  ├─ asyncio.gather(
  │    _scan_airplay()   →  pyatv.scan()           (native async)
  │    _scan_cast()      →  asyncio.to_thread(
  │                           pychromecast.get_chromecasts())
  │  )
  │
  ▼
[{name, address, identifier, device_type, protocols}, ...]
```

## Concurrency Model

- All `CastAgent` methods are `async` — designed for a single asyncio event loop
- `AirPlayBackend` uses native pyatv async throughout
- `GoogleCastBackend` bridges sync pychromecast with `asyncio.to_thread()`
- `FileServer` is aiohttp-based and runs in the same event loop
- Multiple devices can be connected simultaneously via `agent.devices` dict

## Error Handling Strategy

| Error type | Where raised | Consumer behaviour |
|---|---|---|
| `ValueError` | Validation helpers, send_key for Cast | Caught in MCP/CLI, returned as message |
| `FileNotFoundError` | `_validate_media_file`, `_validate_image_file` | Caught in MCP/CLI |
| `RuntimeError` | ffmpeg failure in display_image | Caught in MCP, propagated in CLI |
| `Exception` | Backend connection/network errors | Logged + returned as message in MCP |
