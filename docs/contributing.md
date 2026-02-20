# Contributing

## Dev Setup

```bash
git clone https://github.com/flound1129/castmasta.git
cd castmasta
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**System dependencies:**
- `ffmpeg` — required for `display_image` (not needed to run tests)
- Python 3.10+

## Running Tests

```bash
.venv/bin/pytest tests/ -v
```

All 46 tests run against mocked backends — no real devices required.

To run a specific module:
```bash
.venv/bin/pytest tests/test_agent.py -v
.venv/bin/pytest tests/test_cast_backend.py -v
```

## Project Structure

```
castmasta/
├── agent.py            # CastAgent unified facade
├── backend.py          # DeviceBackend ABC
├── airplay_backend.py  # AirPlay (pyatv)
├── cast_backend.py     # Google Cast (pychromecast)
├── file_server.py      # HTTP server for Cast local streaming
├── credentials.py      # Credential storage
├── config.py           # AgentConfig, DeviceConfig
├── cli.py              # Click CLI
├── mcp_server.py       # FastMCP server
└── tools.py            # LLM tool definitions

tests/
├── test_agent.py
├── test_airplay_backend.py
├── test_backend.py
├── test_cast_backend.py
├── test_credentials.py
└── test_file_server.py

docs/
├── architecture.md     # Module map, design decisions, data flows
├── api.md              # Python API reference
├── contributing.md     # This file
└── plans/              # Implementation plans (historical)
```

## Adding a New Backend

1. Create `castmasta/my_backend.py` implementing `DeviceBackend`:

```python
from .backend import DeviceBackend

class MyProtocolBackend(DeviceBackend):
    device_type = "myprotocol"

    async def connect(self, identifier: str, address: str, name: str, **kwargs) -> None:
        ...

    # implement all 13 remaining abstract methods
```

2. Add `tests/test_my_backend.py` covering at minimum: device_type, connect, disconnect, play, pause, set_volume, get_volume.

3. Update `CastAgent.connect()` to instantiate the new backend when `device_type == "myprotocol"`.

4. Update `CastAgent._scan_cast()` or add a `_scan_myprotocol()` coroutine, then add it to `asyncio.gather()` in `scan()`.

5. Update `usage.md` supported devices list.

## Adding a New CastAgent Method

1. Add the method to `castmasta/agent.py` using an existing method as a template.
2. Add a tool definition to `castmasta/tools.py` (JSON schema).
3. Add an MCP tool to `castmasta/mcp_server.py` (with try/except, return string).
4. Add a CLI command to `castmasta/cli.py` (Click command, asyncio.run).
5. Add tests to `tests/test_agent.py`.
6. Update `usage.md` and `docs/api.md`.

## Code Style

- Python 3.10+ — use `dict[str, T]` and `list[T]` (not `Dict`, `List`)
- All device operations are `async`; keep that contract
- Synchronous pychromecast calls always go through `asyncio.to_thread()`
- Error messages must be actionable (say what was wrong and what's allowed)
- No bare `except Exception as e` in new code — either log+return in MCP tools, or let propagate

## Testing Conventions

- Backend tests: use `AsyncMock` for anything that will be `await`-ed
- Agent tests: inject mocked backends directly into `agent.devices[id] = mock`
- File server tests: use unique high ports (18089+) to avoid collisions
- Never test against real devices in the test suite

## Security Checklist

Before merging any PR that touches file paths or subprocess calls:

- [ ] File paths go through `Path.resolve()` before use
- [ ] Symlink traversal is blocked (`path.is_symlink()` check)
- [ ] File extension is validated against an allowlist
- [ ] Subprocess uses `create_subprocess_exec` (not `shell=True`)
- [ ] Temp files created with `0o600` permissions
- [ ] Credentials stored with `0o600` file / `0o700` directory
