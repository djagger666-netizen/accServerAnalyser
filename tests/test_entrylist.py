import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.log_monitor import LogMonitorService

ENTRYLIST = {
    "entries": [
        {
            "raceNumber": 44,
            "drivers": [
                {"playerId": "S76561198000000000", "shortName": "JD"}
            ],
        }
    ]
}


@pytest.fixture()
def app(tmp_path):
    class TestCfg:
        SECRET_KEY = "test"
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "test.db")
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        ACC_LOG_PATH = str(tmp_path / "server.log")
        ENTRYLIST_PATH = str(tmp_path / "entrylist.json")
        HOST = "127.0.0.1"
        PORT = 5000

    return create_app(TestCfg, start_monitor=False)


def make_monitor(app, entrylist_path):
    return LogMonitorService(app, "unused.log", str(entrylist_path))


def test_entrylist_utf16_with_bom(tmp_path, app):
    p = tmp_path / "entrylist.json"
    p.write_bytes(b"\xff\xfe" + json.dumps(ENTRYLIST).encode("utf-16-le"))
    m = make_monitor(app, p)
    m.load_mapping()
    assert m.car_to_driver_map[44]["steam_id"] == "S76561198000000000"
    assert m.car_to_driver_map[44]["short_name"] == "JD"


def test_entrylist_utf8_with_bom(tmp_path, app):
    p = tmp_path / "entrylist.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(ENTRYLIST).encode("utf-8"))
    m = make_monitor(app, p)
    m.load_mapping()
    assert m.car_to_driver_map[44]["steam_id"] == "S76561198000000000"


def test_entrylist_utf8_no_bom(tmp_path, app):
    p = tmp_path / "entrylist.json"
    p.write_text(json.dumps(ENTRYLIST), encoding="utf-8")
    m = make_monitor(app, p)
    m.load_mapping()
    assert m.car_to_driver_map[44]["short_name"] == "JD"


def test_run_survives_broken_entrylist(tmp_path, app):
    p = tmp_path / "entrylist.json"
    p.write_bytes(b"\xff\xfe{not json")
    log = tmp_path / "server.log"
    log.write_text("Track spa was set and updated\n", encoding="utf-8")
    m = LogMonitorService(app, str(log), str(p))
    m.running = False  # un seul passage suffit pour le test
    m.run()  # ne doit pas lever d'exception
    assert m.car_to_driver_map == {}
