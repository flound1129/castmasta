#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VOICES_SRC="$HOME/.local/share/piper-voices"
VOICE="en_US-lessac-medium"

echo "==> Preparing voice models..."
mkdir -p "$REPO_ROOT/debian/voices"
cp "$VOICES_SRC/$VOICE.onnx" "$REPO_ROOT/debian/voices/"
cp "$VOICES_SRC/$VOICE.onnx.json" "$REPO_ROOT/debian/voices/"

mkdir -p "$REPO_ROOT/dist"

echo "==> Building arm64 deb in Docker..."
docker run --rm \
    --network=host \
    --platform linux/arm64 \
    -v "$REPO_ROOT:/build" \
    arm64v8/debian:trixie \
    bash -c "
        set -e
        apt-get update -qq
        apt-get install -y -qq --no-install-recommends \
            debhelper \
            dh-virtualenv \
            python3-dev \
            python3-pip \
            python3-venv \
            libssl-dev \
            libffi-dev \
            libasound2-dev \
            build-essential \
            patchelf \
            git
        cd /build
        dpkg-buildpackage -us -uc -b
        cp /build/../castmasta_*.deb /build/dist/
    "

echo "==> Done! Package in dist/:"
ls -lh "$REPO_ROOT/dist/"*.deb
