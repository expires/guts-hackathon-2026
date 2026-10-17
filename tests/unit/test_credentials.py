import json
import stat

from playyourself.adapters.aggregator import build_adapters, effective_modes
from playyourself.adapters.credentials import CredentialStore, mask
from playyourself.settings import Settings

SECRET = "tok_abcdefghijklmnop1234"


def test_memory_only_by_default(tmp_path):
    s = CredentialStore(tmp_path)
    s.set("monzo", {"access_token": SECRET})
    assert s.status("monzo").connected and not s.status("monzo").remembered
    assert not (tmp_path / "credentials.json").exists()
    assert not CredentialStore(tmp_path).status("monzo").connected


def test_remember_writes_0600_and_reloads(tmp_path):
    d = tmp_path / "private"
    s = CredentialStore(d)
    s.set("trading212", {"api_key": SECRET, "api_secret": "sec"}, remember=True)
    f = d / "credentials.json"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    again = CredentialStore(d)
    assert again.get("trading212") == {"api_key": SECRET, "api_secret": "sec"}
    assert again.status("trading212").remembered


def test_forget_removes_memory_and_disk(tmp_path):
    s = CredentialStore(tmp_path)
    s.set("monzo", {"access_token": SECRET}, remember=True)
    s.set("trading212", {"api_key": SECRET + "x"}, remember=True)
    s.forget("monzo")
    assert not s.status("monzo").connected
    on_disk = json.loads((tmp_path / "credentials.json").read_text())
    assert list(on_disk) == ["trading212"]
    s.forget("trading212")
    assert not (tmp_path / "credentials.json").exists()


def test_status_is_masked(tmp_path):
    s = CredentialStore(tmp_path)
    s.set("monzo", {"access_token": SECRET, "refresh_token": "refresh_secret_value"})
    dumped = s.status("monzo").model_dump_json()
    assert SECRET not in dumped and "refresh_secret_value" not in dumped
    assert s.status("monzo").hint == "…1234"
    assert mask("short") == "…"


def test_env_fallback_and_stored_wins():
    settings = Settings(_env_file=None, t212_api_key="envkey_0123456789", t212_api_secret="es")
    s = CredentialStore(None, settings)
    assert s.status("trading212").origin == "env" and s.resolve("trading212")["api_secret"] == "es"
    assert effective_modes(settings, s) == {"monzo": "demo", "trading212": "live"}
    s.set("trading212", {"api_key": "stored_key_0123456"})
    assert s.resolve("trading212")["api_key"] == "stored_key_0123456"


def test_build_adapters_uses_store():
    settings = Settings(_env_file=None)
    s = CredentialStore(None, settings)
    assert [a.mode for a in build_adapters(settings, s)] == ["demo", "demo"]
    s.set("monzo", {"access_token": "t"})
    ads = build_adapters(settings, s)
    assert [a.mode for a in ads] == ["live", "demo"]
    assert ads[0].cache_key == "monzo-live" and ads[1].cache_key.startswith("trading212-mock-")


def test_corrupt_file_ignored(tmp_path):
    (tmp_path / "credentials.json").write_text("not json")
    assert not CredentialStore(tmp_path).status("monzo").connected
