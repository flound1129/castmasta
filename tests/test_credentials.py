import os
import pytest
from castmasta.credentials import CredentialStore


@pytest.fixture
def cred_store(tmp_path):
    path = str(tmp_path / "creds.json")
    return CredentialStore(storage_path=path)


def test_set_and_get(cred_store):
    cred_store.set("dev1", "AirPlay", "secret123")
    assert cred_store.get("dev1", "AirPlay") == "secret123"


def test_get_missing(cred_store):
    assert cred_store.get("nonexistent", "AirPlay") is None


def test_delete_specific_protocol(cred_store):
    cred_store.set("dev1", "AirPlay", "secret1")
    cred_store.set("dev1", "Companion", "secret2")
    cred_store.delete("dev1", "AirPlay")
    assert cred_store.get("dev1", "AirPlay") is None
    assert cred_store.get("dev1", "Companion") == "secret2"


def test_delete_all_protocols(cred_store):
    cred_store.set("dev1", "AirPlay", "secret1")
    cred_store.set("dev1", "Companion", "secret2")
    cred_store.delete("dev1")
    assert cred_store.get("dev1", "AirPlay") is None
    assert cred_store.get("dev1", "Companion") is None


def test_persistence(tmp_path):
    path = str(tmp_path / "creds.json")
    store1 = CredentialStore(storage_path=path)
    store1.set("dev1", "AirPlay", "secret123")
    store2 = CredentialStore(storage_path=path)
    assert store2.get("dev1", "AirPlay") == "secret123"


def test_file_permissions(tmp_path):
    path = str(tmp_path / "creds.json")
    store = CredentialStore(storage_path=path)
    store.set("dev1", "AirPlay", "secret123")
    stat = os.stat(path)
    assert oct(stat.st_mode & 0o777) == "0o600"
