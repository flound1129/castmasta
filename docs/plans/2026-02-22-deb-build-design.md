# Debian Package Build Design

**Date:** 2026-02-22
**Target:** Raspbian Trixie, arm64 (Raspberry Pi home server)

## Goal

Produce a `.deb` package for castmasta that installs as a systemd service listening on `0.0.0.0:16384`, self-contained with all Python dependencies and the default piper voice model bundled.

## Approach

Use `dh-virtualenv` to bundle a complete Python virtualenv (all pip deps including `piper-tts` binary) inside the `.deb`. Build runs in an arm64 Docker container with `--network=host`. A `scripts/build-deb.sh` script handles the build and drops the `.deb` in `dist/`.

## Package Contents

| Content | Path |
|---|---|
| Venv (arch-specific binaries, piper binary) | `/usr/lib/castmasta/` |
| Default voice model (`en_US-lessac-medium`) | `/usr/share/castmasta/voices/` |
| CLI binary | `/usr/bin/castmasta` |
| MCP server binary | `/usr/bin/castmasta-mcp` |
| Systemd unit | `/usr/lib/systemd/system/castmasta.service` |
| Credentials & state | `/var/lib/castmasta/` |
| Config | `/etc/castmasta/` |
| Logs | systemd journal |

## Service

- Runs `castmasta-mcp --host 0.0.0.0 --port 16384`
- Runs as dedicated unprivileged system user `castmasta` (no login shell)
- `postinst` creates the `castmasta` user and sets ownership on `/var/lib/castmasta/`
- Restarts on failure (`Restart=on-failure`)
- Enabled on install via `deb-systemd-helper`

## MCP Server Changes

- Add `--host` / `--port` CLI args to `castmasta-mcp` (defaults: `0.0.0.0`, `16384`)
- `PIPER_VOICE_DATA_DIR` falls back to `/usr/share/castmasta/voices/` when the user-local path doesn't exist

## Build

- Docker image: `arm64v8/debian:trixie`
- `scripts/build-deb.sh`: pulls image, runs `dpkg-buildpackage` inside container, copies `.deb` to `dist/`
- `debian/` directory: `control`, `rules`, `compat`, `postinst`, `prerm`, `castmasta.service`
- System deps declared in `debian/control`: `python3`, `python3-dev`, `libssl-dev`, `libffi-dev`, `libasound2`

## Voice Model Bundling

- `en_US-lessac-medium.onnx` and `.onnx.json` copied from host into `debian/voices/` at build time
- Installed to `/usr/share/castmasta/voices/`
- `PIPER_VOICE_DATA_DIR` in `agent.py` checks user-local path first, then falls back to system path

## Not Included

- Additional piper voice models (can be downloaded manually to `~/.local/share/piper-voices/`)
- GUI or web interface
