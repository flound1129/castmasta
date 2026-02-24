# Device Pairing and Authentication

CastMasta uses pyatv for AirPlay device communication. Most AirPlay devices require
one-time pairing before they will accept streaming or remote-control commands.

## When is pairing needed?

- **Apple TV**: Always requires pairing for AirPlay and Companion protocols.
- **HomePod / AirPort Express**: Requires AirPlay pairing.
- **Onkyo / other AV receivers**: Some accept connections without pairing.
- **Google Cast (Chromecast)**: No pairing required — uses mDNS discovery only.

A connection attempt on an unpaired device returns HTTP 470 from pyatv.

---

## How pairing works

Pairing is a two-step process over the network:

1. **Initiate** (`pair_device` / `agent.pair()`):
   - Opens a pyatv pairing session to the device.
   - The Apple TV displays a 4-digit PIN on screen (or the device generates one and
     expects you to enter it — see `device_provides_pin` below).
   - The session is held open in `agent._pairing_handlers` until step 2.

2. **Complete** (`pair_device_with_pin` / `agent.pair_with_pin()`):
   - Submits the PIN to the open session.
   - pyatv negotiates credentials with the device.
   - On success, credentials are saved to the credential store.
   - The session is closed and removed from `_pairing_handlers`.

### `device_provides_pin`

This flag indicates *who* generates the PIN:

| `device_provides_pin` | Meaning |
|---|---|
| `True` | Device shows PIN on screen — user reads it and calls `pair_device_with_pin` |
| `False` | Device expects you to choose a PIN — display it to the user, then call `pair_device_with_pin` with that PIN |

---

## Credential storage

Credentials are stored as a JSON file:

| Environment | Path |
|---|---|
| Dev / user | `~/.castmasta/credentials.json` |
| systemd service | `/var/lib/castmasta/credentials.json` (via `storage_path` in `AgentConfig`) |

The file and its parent directory are created with mode `0700`/`0600` (owner-only).

Credentials are keyed by `<identifier>:<protocol>`, e.g.:
```json
{
  "C2:BA:9F:70:DB:F7:AirPlay": "...",
  "C2:BA:9F:70:DB:F7:Companion": "..."
}
```

Credentials are loaded on `connect()` and passed to pyatv for authentication.

---

## Protocols

Two protocols can be paired independently:

| Protocol | Port | Used for |
|---|---|---|
| `airplay` | 7000 | Streaming audio/video, `stream_file`, `announce` |
| `companion` | 49153 | Remote control — `send_key`, power, media controls |

Pair both protocols to use all features.

---

## mDNS vs. host-based pairing

By default, `pair_device` scans the network via mDNS to find the device. If mDNS
multicast is unavailable (e.g. running from a systemd service on a Pi), pass the
device's IP address directly to bypass the scan:

```bash
# MCP call with host parameter
pair_device(name="Home Theater", host="<device-ip>")
pair_device_with_pin(name="Home Theater", pin="1234", host="<device-ip>")
```

The `host` parameter triggers a unicast scan (`pyatv.scan(hosts=[ip])`) to the
specific device instead of a broadcast mDNS scan.

---

## CLI pairing

```bash
# Not yet exposed as a CLI command — use MCP or the Python API directly.
```

## MCP pairing

```
# Step 1: initiate pairing (Apple TV shows PIN on screen)
pair_device(name="Home Theater")
# or with explicit host if mDNS isn't working:
pair_device(name="Home Theater", host="<device-ip>")

# Step 2: complete with PIN shown on device
pair_device_with_pin(name="Home Theater", pin="1234")
# or:
pair_device_with_pin(name="Home Theater", pin="1234", host="<device-ip>")
```

## Python API

```python
from castmasta import CastAgent
from pyatv.const import Protocol

agent = CastAgent()

# Scan or provide address directly
devices = await agent.scan(hosts=["<device-ip>"])
dev = devices[0]

# Step 1
result = await agent.pair(dev["identifier"], dev["address"], dev["name"], Protocol.AirPlay)
print(result["status"])  # "pin_required"

# Step 2 (after user reads PIN from screen)
success = await agent.pair_with_pin(dev["identifier"], dev["address"], dev["name"], "1234", Protocol.AirPlay)
print("Paired:", success)
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `HTTP 470` on connect | Device not paired | Run `pair_device` |
| `No active pairing session` | Called `pair_device_with_pin` without `pair_device` first | Call `pair_device` first |
| `Device not found` from `pair_device` | mDNS scan failed | Pass `host=<ip>` |
| Pairing fails silently | Wrong PIN | Try again with correct PIN |
| Credentials lost after reboot | Wrong `storage_path` | Check `AgentConfig.storage_path`; for the service it must be `/var/lib/castmasta/credentials.json` |
