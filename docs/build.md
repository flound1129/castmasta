# Building castmasta

## Prerequisites

- Docker with arm64/linux platform support (e.g. Docker Desktop with multi-arch, or native arm64 host)
- `en_US-lessac-medium` piper voice model at `~/.local/share/piper-voices/`

## Build

```bash
scripts/build-deb.sh
```

Output: `dist/castmasta_<version>_arm64.deb`

## Install on Pi

```bash
scp dist/castmasta_*.deb pi@<host>:~
ssh pi@<host> sudo apt install ./castmasta_*.deb
```

## Service management

```bash
sudo systemctl status castmasta
sudo systemctl restart castmasta
sudo journalctl -u castmasta -f
```

## Pairing devices

After install, run pairing as the `castmasta` user:

```bash
sudo -u castmasta /usr/lib/castmasta/bin/castmasta pair "Device Name"
```

Credentials are stored in `/var/lib/castmasta/credentials.json`.
