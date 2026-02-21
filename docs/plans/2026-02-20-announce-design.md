# Design: Announce (Text-to-Speech) Feature

## Overview

Add an `announce(identifier, text, voice)` method to `CastAgent` that converts text to speech using Piper TTS and streams the resulting audio to any connected AirPlay or Google Cast device.

## Approach

Run Piper TTS as a subprocess (same pattern as `display_image` uses ffmpeg), write WAV output to a temp file, then stream it via the existing `backend.stream_file()` infrastructure. Clean up the temp file in a `finally` block.

## Components

### `castmasta/agent.py`
- Add `PIPER_VOICE_DATA_DIR = Path.home() / ".local/share/piper-voices"`
- Add `DEFAULT_VOICE = "en_US-lessac-medium"`
- Add `async def announce(self, identifier, text, voice=DEFAULT_VOICE)`:
  - Validate text (non-empty string, max length guard)
  - Validate voice (non-empty string, no path separators)
  - `tempfile.mkstemp(suffix=".wav")` with `chmod 0o600`
  - `asyncio.create_subprocess_exec` with piper, stdin=text bytes
  - Check returncode, raise RuntimeError on failure
  - `await backend.stream_file(tmp_path)`
  - `finally: os.unlink(tmp_path)`

### `castmasta/tools.py`
- Add `announce` JSON schema: identifier (required), text (required), voice (optional)

### `castmasta/mcp_server.py`
- Add announce MCP tool

### `castmasta/cli.py`
- Add `announce` CLI command with --voice option

### `pyproject.toml`
- Add `piper-tts>=1.2` to dependencies

## Error Handling

- Empty text: ValueError before any subprocess
- Invalid voice (path chars): ValueError before any subprocess
- Piper not installed: RuntimeError with clear message
- Piper exits non-zero: RuntimeError with stderr
- Device not connected: ValueError from _get_backend

## Non-goals

- No WAV caching (can be added later)
- No voice model auto-download (models must be pre-installed)
