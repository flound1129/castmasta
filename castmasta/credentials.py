"""Credential storage for device pairing."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CredentialStore:
    """Store and retrieve device credentials."""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".castmasta" / "credentials.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.storage_path.parent, 0o700)
        self._credentials: dict = self._load()

    def _load(self) -> dict:
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self):
        dir_ = self.storage_path.parent
        fd = None
        tmp_path = None
        try:
            fd = tempfile.mkstemp(dir=dir_, suffix=".tmp")
            tmp_path = fd[1]
            with os.fdopen(fd[0], "w") as f:
                json.dump(self._credentials, f, indent=2)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.storage_path)
        except OSError:
            logger.exception("Failed to save credentials")
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get(self, identifier: str, protocol: str) -> Optional[str]:
        key = f"{identifier}:{protocol}"
        return self._credentials.get(key)

    def set(self, identifier: str, protocol: str, credentials: str):
        key = f"{identifier}:{protocol}"
        self._credentials[key] = credentials
        self._save()

    def delete(self, identifier: str, protocol: Optional[str] = None):
        if protocol:
            key = f"{identifier}:{protocol}"
            self._credentials.pop(key, None)
        else:
            keys_to_delete = [
                k for k in self._credentials if k.startswith(f"{identifier}:")
            ]
            for key in keys_to_delete:
                del self._credentials[key]
        self._save()
