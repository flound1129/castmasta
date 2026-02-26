#!/usr/bin/env bash
# Register castmasta with bigbrain port registry.
# Reads FLEET_TOKEN from /etc/castmasta/env (or environment).
# Generates an Ed25519 keypair on first run and stores the private
# key at /var/lib/castmasta/bigbrain.key.
set -euo pipefail

BIGBRAIN_URL="${BIGBRAIN_URL:-http://10.0.0.14:8808}"
SERVICE_NAME="castmasta"
REQUESTED_PORT=16384
KEY_PATH="/var/lib/castmasta/bigbrain.key"
PYTHON="/usr/lib/castmasta/bin/python"
ENV_FILE="/etc/castmasta/env"

# Load env file
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

if [[ -z "${FLEET_TOKEN:-}" ]]; then
    echo "Error: FLEET_TOKEN not set. Add it to .env or export it." >&2
    exit 1
fi

echo "==> Enrolling ${SERVICE_NAME} with bigbrain at ${BIGBRAIN_URL}"

exec "$PYTHON" - "$BIGBRAIN_URL" "$SERVICE_NAME" "$REQUESTED_PORT" "$KEY_PATH" "$FLEET_TOKEN" <<'PYEOF'
import base64, hashlib, hmac, json, os, sys, time, urllib.request

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

bigbrain_url = sys.argv[1]
service_name = sys.argv[2]
requested_port = int(sys.argv[3])
key_path = sys.argv[4]
fleet_token = sys.argv[5]

# --- Load or generate keypair ---
if os.path.exists(key_path):
    with open(key_path) as f:
        priv_b64 = f.read().strip()
    priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(priv_b64))
    print(f"Loaded existing keypair from {key_path}")
else:
    priv = Ed25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        f.write(priv_b64)
    print(f"Generated new keypair, saved to {key_path}")

pub_b64 = base64.b64encode(
    priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
).decode()

# --- Enroll ---
timestamp = str(int(time.time()))
body_dict = {"service": service_name, "port": requested_port}
body = json.dumps(body_dict)
signed_data = f"POST\n/enroll\n{timestamp}\n{body}".encode()
signature = hmac.new(fleet_token.encode(), signed_data, hashlib.sha256).hexdigest()

req = urllib.request.Request(
    f"{bigbrain_url}/enroll",
    data=body.encode(),
    headers={
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-Signature": signature,
        "X-Public-Key": pub_b64,
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    print(f"Enrolled: {result['service']} -> port {result['port']}")
except urllib.error.HTTPError as e:
    body_text = e.read().decode()
    print(f"Error {e.code}: {body_text}", file=sys.stderr)
    sys.exit(1)
PYEOF
