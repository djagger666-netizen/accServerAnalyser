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
