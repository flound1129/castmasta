#!/usr/bin/env bash
# Build the cached arm64 builder image. Run this once (or after changing build deps).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Building castmasta-builder arm64 base image..."
docker build \
    --platform linux/arm64 \
    --network=host \
    -t castmasta-builder:latest \
    -f "$REPO_ROOT/Dockerfile.build" \
    "$REPO_ROOT"

echo "==> Done. Run scripts/build-deb.sh to build the package."
