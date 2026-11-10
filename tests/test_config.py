import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config


def test_relative_paths_resolve_against_repo_root(monkeypatch):
    monkeypatch.setenv("ACC_LOG_PATH", os.path.join("..", "accweb_v1.27.0", "config", "1786545622", "log", "server.log"))
    monkeypatch.setenv("ENTRYLIST_PATH", os.path.join("..", "accweb_v1.27.0", "config", "1786545622", "cfg", "entrylist.json"))
    importlib.reload(config)
    assert config.Config.ACC_LOG_PATH == os.path.normpath(
        os.path.join(config.BASE_DIR, "..", "accweb_v1.27.0", "config", "1786545622", "log", "server.log")
    )
    assert config.Config.ENTRYLIST_PATH.endswith(
        os.path.join("accweb_v1.27.0", "config", "1786545622", "cfg", "entrylist.json")
    )
    monkeypatch.delenv("ACC_LOG_PATH")
    monkeypatch.delenv("ENTRYLIST_PATH")
    importlib.reload(config)


def test_absolute_path_kept_as_is(monkeypatch):
    abs_path = os.path.join("D:\\", "serveur", "log", "server.log") if os.name == "nt" else "/serveur/log/server.log"
    monkeypatch.setenv("ACC_LOG_PATH", abs_path)
    importlib.reload(config)
    assert config.Config.ACC_LOG_PATH == abs_path
    monkeypatch.delenv("ACC_LOG_PATH")
    importlib.reload(config)


def test_local_config_file_overrides(tmp_path):
    local = tmp_path / "config.local.py"
    local.write_text(
        'ACC_LOG_PATH = "..\\\\accweb_v1.27.0\\\\log\\\\server.log"\nPORT = 9999\n',
        encoding="utf-8",
    )

    class Dummy:
        ACC_LOG_PATH = "defaut"
        PORT = 5000

    config._apply_local_overrides(Dummy, str(local))
    assert Dummy.PORT == 9999
    assert config._resolve(Dummy.ACC_LOG_PATH) == os.path.normpath(
        os.path.join(config.BASE_DIR, "..", "accweb_v1.27.0", "log", "server.log")
    )


def test_local_config_file_absent_is_noop(tmp_path):
    class Dummy:
        PORT = 5000

    config._apply_local_overrides(Dummy, str(tmp_path / "inexistant.py"))
    assert Dummy.PORT == 5000
