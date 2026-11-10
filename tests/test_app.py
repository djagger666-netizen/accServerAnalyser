import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.log_monitor import LogMonitorService
from app.models import Drivers, LapLive, Races

SAMPLE_LOG = """\
Track monza was set and updated
Session changed: Practice 0 -> Qualifying 0
New connection request: id 3 John Doe S76561198000000000 on car model 20
Creating new car connection: carId 5, carModel 20, raceNumber #44
Lap carId 5, driverId 1, lapTime 1:35:791, timestampMS 35791.000000, flags: 0, S1 0:30:123, S2 0:32:456, S3 0:33:212, fuel 45.2
Lap carId 5, driverId 1, lapTime 1:34:500, timestampMS 70291.000000, flags: 0, fuel 43.1, hasCut
Lap carId 5, driverId 1, lapTime 35791:23:647, timestampMS 71000.000000, flags: 0, S1 0:30:000, fuel 0.0
Session changed: Qualifying -> Race 0
Lap carId 5, driverId 1, lapTime 1:36:100, timestampMS 200000.0, flags: 0, fuel 30.0
Detected sessionPhase <session overtime> -> <session completed> (Race)
"""


@pytest.fixture()
def app(tmp_path):
    log_path = tmp_path / "server.log"
    log_path.write_text(SAMPLE_LOG, encoding="utf-8")

    class TestCfg:
        SECRET_KEY = "test"
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "test.db")
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        ACC_LOG_PATH = str(log_path)
        ENTRYLIST_PATH = str(tmp_path / "entrylist.json")
        HOST = "127.0.0.1"
        PORT = 5000

    application = create_app(TestCfg, start_monitor=False)
    monitor = LogMonitorService(
        application, str(log_path), str(tmp_path / "entrylist.json")
    )
    with application.app_context():
        monitor.tail_file(str(log_path))
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_log_parsing_populates_db(app):
    with app.app_context():
        assert Races.query.count() == 2  # Qualifying + Race
        assert Drivers.query.count() == 1
        driver = Drivers.query.first()
        assert driver.player_id == "76561198000000000"
        assert driver.car_id == 5
        # la ligne sentinel 35791:23:647 est ignoree
        assert LapLive.query.count() == 3
        cut_laps = LapLive.query.filter_by(hasCut=True).all()
        assert len(cut_laps) == 1
        assert cut_laps[0].lap_time == 94500
        race = Races.query.order_by(Races.id.desc()).first()
        assert race.race_session == "Race Completed"


def test_routes_return_200(client):
    for url in ("/", "/races", "/live", "/drivers", "/servers", "/api/live_data"):
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"


def test_race_detail_and_driver_pages(client, app):
    with app.app_context():
        race_id = Races.query.order_by(Races.id.desc()).first().id
        driver_id = Drivers.query.first().id
    assert client.get(f"/race/{race_id}").status_code == 200
    assert client.get(f"/driver/{driver_id}").status_code == 200
    assert client.get("/race/9999").status_code == 404


def test_live_api_contains_laps(client, app):
    with app.app_context():
        race = Races.query.order_by(Races.id.desc()).first()
        expected_race_id = race.id
    resp = client.get("/api/live_data")
    data = resp.get_json()
    assert data["race"]["id"] == expected_race_id
    assert data["race"]["piste"] == "monza"
    assert len(data["laps"]) == 1  # un seul tour valide dans la session Race
    assert data["laps"][0]["driver"] == "John Doe"
    assert data["laps"][0]["lap_time"] == 96100
