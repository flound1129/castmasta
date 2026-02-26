#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VOICES_SRC="$HOME/.local/share/piper-voices"
VOICE="en_US-lessac-medium"
TS="$(date +%s)"
VERSION="0.${TS}"
DEB_DATE="$(date -R)"
BUILDER_IMAGE="castmasta-builder:latest"

echo "==> Version: ${VERSION}"

# Update pyproject.toml version
sed -i "s/^version = .*/version = \"${VERSION}\"/" "$REPO_ROOT/pyproject.toml"

# Prepend changelog entry
CHANGELOG_ENTRY="castmasta (${VERSION}-1) trixie; urgency=low

  * Automated build.

 -- Adam <adam@localhost>  ${DEB_DATE}

"
printf '%s' "$CHANGELOG_ENTRY" | cat - "$REPO_ROOT/debian/changelog" > /tmp/changelog.new
mv /tmp/changelog.new "$REPO_ROOT/debian/changelog"

echo "==> Preparing voice models..."
mkdir -p "$REPO_ROOT/debian/voices"
cp "$VOICES_SRC/$VOICE.onnx" "$REPO_ROOT/debian/voices/"
cp "$VOICES_SRC/$VOICE.onnx.json" "$REPO_ROOT/debian/voices/"

mkdir -p "$REPO_ROOT/dist"

# Build base image if not present
if ! docker image inspect "$BUILDER_IMAGE" > /dev/null 2>&1; then
    echo "==> Builder image not found, building it first..."
    "$REPO_ROOT/scripts/build-base-image.sh"
fi

echo "==> Building arm64 deb in Docker (using cached builder image)..."
docker run --rm \
    --network=host \
    --platform linux/arm64 \
    -v "$REPO_ROOT:/build" \
    "$BUILDER_IMAGE" \
    bash -c "
        set -e
        cd /build
        dpkg-buildpackage -us -uc -b
        cp /build/../castmasta_*.deb /build/dist/
    "

# Rename to include codename: <pkg>_<ver>_<codename>_<arch>.deb
for f in "$REPO_ROOT/dist/"castmasta_*_arm64.deb; do
    newname=$(echo "$f" | sed 's/_arm64\.deb$/_trixie_arm64.deb/')
    [ "$f" != "$newname" ] && mv "$f" "$newname"
done

echo "==> Done! Package in dist/:"
ls -lh "$REPO_ROOT/dist/"*_trixie_arm64.deb
