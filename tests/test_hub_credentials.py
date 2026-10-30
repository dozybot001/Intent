import json
import os
import stat
import subprocess

import pytest

from intent_cli.hub.credentials import (
    CredentialStoreError,
    GlobalHubConfigError,
    credentials_file,
    erase_access_token,
    global_api_base_url,
    global_config_path,
    load_access_token,
    normalize_api_base_url,
    read_global_hub_config,
    store_access_token,
    write_global_hub_config,
)


def _configure_test_credential_store(monkeypatch, tmp_path):
    git_config = tmp_path / "gitconfig"
    credential_file = tmp_path / "credentials"
    subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(git_config),
            "credential.helper",
            f"store --file={credential_file}",
        ],
        check=True,
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(git_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return credential_file


def test_global_config_stores_only_normalized_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("INTENT_CONFIG_HOME", str(tmp_path / "intent-config"))

    write_global_hub_config("HTTPS://INTHUB.TENON.ASIA/")

    assert global_api_base_url() == "https://inthub.tenon.asia"
    assert read_global_hub_config() == {"api_base_url": "https://inthub.tenon.asia"}
    assert json.loads(global_config_path().read_text(encoding="utf-8")) == {
        "api_base_url": "https://inthub.tenon.asia"
    }
    assert global_config_path().stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "value",
    [
        "",
        "inthub.tenon.asia",
        "ftp://inthub.tenon.asia",
        "https://user:secret@inthub.tenon.asia",
        "https://inthub.tenon.asia?q=secret",
        "https://inthub.tenon.asia/#fragment",
        "https://inthub.tenon.asia\npassword=injected",
    ],
)
def test_api_base_url_rejects_unsafe_values(value):
    with pytest.raises(GlobalHubConfigError):
        normalize_api_base_url(value)


def test_git_credential_helper_round_trip(monkeypatch, tmp_path):
    credential_file = _configure_test_credential_store(monkeypatch, tmp_path)
    api_base_url = "https://inthub.tenon.asia"
    token = "ith_pat_test-secret"

    store_access_token(api_base_url, token)

    assert load_access_token(api_base_url) == token
    assert token in credential_file.read_text(encoding="utf-8")

    erase_access_token(api_base_url)

    assert load_access_token(api_base_url) is None


def test_a_machine_without_a_helper_keeps_the_token_in_a_private_file(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "missing-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    url = "https://inthub.tenon.asia"

    assert store_access_token(url, "ith_pat_filed") == "file"
    path = credentials_file()
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_access_token(url) == "ith_pat_filed"
    assert load_access_token("https://other.example") is None, "a token stays with its endpoint"

    store_access_token("https://other.example", "ith_pat_other")
    erase_access_token(url)
    assert load_access_token(url) is None and load_access_token("https://other.example") == "ith_pat_other"
    erase_access_token("https://other.example")
    assert not path.exists()


def test_a_symlinked_credentials_file_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "missing-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    path = credentials_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(CredentialStoreError):
        store_access_token("https://inthub.tenon.asia", "ith_pat_filed")
    assert load_access_token("https://inthub.tenon.asia") is None


def test_store_rejects_credential_protocol_injection():
    with pytest.raises(CredentialStoreError):
        store_access_token(
            "https://inthub.tenon.asia",
            "ith_pat_safe\nusername=attacker",
        )
