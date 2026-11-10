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
        application, str(log_path), str(tmp_path / "entrylist.json"),
        state_path=str(tmp_path / "monitor_state.json"),
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
        # la ligne sentinel 35791:23:647 est enregistrée comme passage de secteur (lap_time NULL)
        assert LapLive.query.count() == 4
        splits = LapLive.query.filter(LapLive.lap_time.is_(None)).all()
        assert len(splits) == 1
        assert splits[0].s1 == 30000
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


def test_race_detail_shows_formatted_times(client, app):
    with app.app_context():
        race_id = Races.query.order_by(Races.id.desc()).first().id
    html = client.get(f"/race/{race_id}").get_data(as_text=True)
    assert "1:36:100" in html  # 96100 ms au format m:ss:mmm


def test_races_grouped_by_weekend(client, app):
    html = client.get("/races").get_data(as_text=True)
    assert "Week-end #1" in html
    assert "/weekend/1" in html


def test_weekend_page_results_and_sessions(client, app):
    resp = client.get("/weekend/1")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # résultats classés par meilleur tour en haut
    assert "Résultats" in html
    assert "Qualifying" in html and "Race" in html
    assert "1:35:791" in html  # meilleur tour qualif (hors cut)
    assert "1:36:100" in html  # meilleur tour race
    # le tour cut 94500 ms (1:34:500) ne compte pas dans les résultats:
    # il n'apparaît que dans le tableau dépliable de la session (1 fois)
    assert html.count("1:34:500") == 1
    assert "John Doe" in html
    # session dépliable + tour cut en rouge
    assert "<details>" in html
    assert "cut-row" in html
    assert client.get("/weekend/9999").status_code == 404


def test_new_time_print_shows_sector(app, tmp_path, capsys):
    log_path = tmp_path / "server.log"
    log_path.write_text(
        "Session changed: Practice 0 -> Race 0\n"
        "Lap carId 5, driverId 1, lapTime 35791:23:647, timestampMS 1000.0, flags: 0, S1 0:30:000, fuel 10.0\n"
        "Lap carId 5, driverId 1, lapTime 35791:23:647, timestampMS 2000.0, flags: 0, S1 0:30:000, S2 0:31:000, fuel 9.0\n"
        "Lap carId 5, driverId 1, lapTime 1:35:791, timestampMS 3000.0, flags: 0, S1 0:30:000, S2 0:31:000, S3 0:34:791, fuel 8.0\n",
        encoding="utf-8",
    )
    monitor = LogMonitorService(
        app, str(log_path), str(tmp_path / "entrylist.json"),
        state_path=str(tmp_path / "state.json"),
    )
    with app.app_context():
        monitor.tail_file(str(log_path))
    out = capsys.readouterr().out
    assert "newTime[S1]" in out
    assert "newTime[S2]" in out
    assert "newTime[tour]" in out


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
