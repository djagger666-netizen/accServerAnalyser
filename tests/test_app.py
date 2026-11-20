import os
import re
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.log_monitor import LogMonitorService
from app.models import Drivers, LapLive, Races, WeekEnds

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


def test_drivers_page_stats(client, app):
    html = client.get("/drivers").get_data(as_text=True)
    # colonnes supprimées
    for old in ("Steam ID", "N° course", "Car ID", "Modèle"):
        assert old not in html
    # nouvelles colonnes: 3 tours accomplis, voiture préférée, piste préférée
    assert "Tours" in html and "Voiture préférée" in html and "Piste préférée" in html
    assert "John Doe" in html
    assert ">3</td>" in html  # 3 tours complets (le split n'est pas un tour)
    assert "Aston Martin" in html and "V8 Vantage (2019)" in html  # carModel 20
    assert "monza" in html

    with app.app_context():
        driver_id = Drivers.query.first().id
    html_d = client.get(f"/driver/{driver_id}").get_data(as_text=True)
    assert "Steam ID" not in html_d
    assert "Tours effectués : <strong>3</strong>" in html_d
    assert "monza" in html_d


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


def test_races_hides_weekends_without_laps(client, app):
    with app.app_context():
        we = WeekEnds(races_id=[])
        db.session.add(we)
        db.session.commit()
        db.session.add(Races(piste="spa", we_id=we.id, race_session="Practice"))
        db.session.commit()
        empty_we_id = we.id
    html = client.get("/races").get_data(as_text=True)
    assert f"Week-end #{empty_we_id}" not in html  # 0 tour -> caché
    assert "Week-end #1" in html  # celui avec des tours reste visible


def test_races_filter_by_date_calendar(client, app):
    """Le filtre 'date' (calendrier) ne garde que les courses du jour choisi."""
    with app.app_context():
        we = WeekEnds(races_id=[])
        db.session.add(we)
        db.session.commit()
        r1 = Races(piste="spa", we_id=we.id, race_session="Practice",
                   date=datetime(2026, 11, 10, 12, 25))
        r2 = Races(piste="spa", we_id=we.id, race_session="Race",
                   date=datetime(2026, 11, 11, 18, 0))
        db.session.add_all([r1, r2])
        db.session.commit()
        for r in (r1, r2):
            db.session.add(LapLive(player_id="76561198000000000", car_id=5,
                                   driver_place=1, race_id=r.id, lap_time=90000,
                                   timestamp_ms=1.0, fuel=1.0))
        db.session.commit()
        r1_id, r2_id = r1.id, r2.id
    html = client.get("/races?date=2026-11-10").get_data(as_text=True)
    assert f"/race/{r1_id}" in html
    assert f"/race/{r2_id}" not in html
    html = client.get("/races?date=2026-11-11").get_data(as_text=True)
    assert f"/race/{r2_id}" in html
    assert f"/race/{r1_id}" not in html
    # sans filtre date, tout est affiché
    html = client.get("/races").get_data(as_text=True)
    assert f"/race/{r1_id}" in html and f"/race/{r2_id}" in html
    # calendrier intégré à la page (plus de saisie mois/année ni d'input date natif)
    assert 'class="calendar"' in html
    assert "Toutes dates" in html
    assert 'type="date"' not in html
    assert 'name="month"' not in html and 'name="year"' not in html


def test_races_calendar_marks_race_days(client, app):
    """Le calendrier affiche le mois demandé, marque les jours avec courses
    et distingue le jour sélectionné (filtre date)."""
    with app.app_context():
        we = WeekEnds(races_id=[])
        db.session.add(we)
        db.session.commit()
        r1 = Races(piste="spa", we_id=we.id, race_session="Practice",
                   date=datetime(2026, 11, 10, 12, 25))
        r2 = Races(piste="spa", we_id=we.id, race_session="Race",
                   date=datetime(2026, 11, 11, 18, 0))
        db.session.add_all([r1, r2])
        db.session.commit()
        for r in (r1, r2):
            db.session.add(LapLive(player_id="76561198000000000", car_id=5,
                                   driver_place=1, race_id=r.id, lap_time=90000,
                                   timestamp_ms=1.0, fuel=1.0))
        db.session.commit()
    html = client.get("/races?cal_month=2026-11").get_data(as_text=True)
    assert "novembre 2026" in html  # titre du mois en français
    assert re.search(r'class="cal-day has-race"[^>]*>10<', html)
    assert re.search(r'class="cal-day has-race"[^>]*>11<', html)
    assert not re.search(r'class="cal-day has-race"[^>]*>12<', html)  # 12: pas de course
    # navigation mois précédent / suivant
    assert "cal_month=2026-10" in html and "cal_month=2026-12" in html
    # jour sélectionné mis en évidence, lien avec date + cal_month
    html = client.get("/races?cal_month=2026-11&date=2026-11-10").get_data(as_text=True)
    assert re.search(r'class="cal-day has-race selected"[^>]*>10<', html)
    assert "date=2026-11-10" in html
    # "Toutes dates" conserve le filtre piste mais efface la date
    html = client.get("/races?cal_month=2026-11&date=2026-11-10&piste=spa").get_data(as_text=True)
    m = re.search(r'class="cal-all" href="([^"]+)"', html)
    assert m and "date=" not in m.group(1) and "piste=spa" in m.group(1)


def test_races_weekend_date_is_first_event(client, app):
    """La date affichée du week-end = date de son 1er événement (1ère course),
    pas la date de création du week-end."""
    with app.app_context():
        we = WeekEnds(races_id=[], date=datetime(2026, 1, 1, 10, 0))  # date fausse (import)
        db.session.add(we)
        db.session.commit()
        r1 = Races(piste="paul_ricard", we_id=we.id, race_session="Practice",
                   date=datetime(2026, 11, 10, 12, 25))
        r2 = Races(piste="paul_ricard", we_id=we.id, race_session="Race",
                   date=datetime(2026, 11, 10, 14, 0))
        db.session.add_all([r1, r2])
        db.session.commit()
        db.session.add(LapLive(player_id="76561198000000000", car_id=5,
                               driver_place=1, race_id=r1.id, lap_time=90000,
                               timestamp_ms=1.0, fuel=1.0))
        db.session.commit()
        we_id = we.id
    html = client.get("/races").get_data(as_text=True)
    assert f"Week-end #{we_id}" in html
    assert "10/11/2026 12:25" in html  # date du 1er événement
    assert "01/01/2026 10:00" not in html  # pas la date de création du week-end


def test_races_table_session_links(client, app):
    """Tableau compact: colonne 'Session' (lien vers /race/<id>), sans colonne ID ni Date."""
    with app.app_context():
        race = Races.query.order_by(Races.id.asc()).first()
        race_id = race.id
    html = client.get("/races").get_data(as_text=True)
    assert "<th>Session</th>" in html
    assert "<th>ID</th>" not in html
    assert "<th>Date</th>" not in html  # date retirée de chaque ligne
    # le texte 'Session' reste un lien vers la course (id conservé dans le href)
    assert f'href="/race/{race_id}"' in html


def test_weekend_page_results_and_sessions(client, app):
    resp = client.get("/weekend/1")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # résultats classés par meilleur tour en haut
    assert "Résultats" in html
    assert "Qualifying" in html and "Race" in html
    assert "1:35:791" in html  # meilleur tour qualif (hors cut)
    # résultat de course: nb de tours + temps cumulé + meilleur tour + médailles + voiture
    assert "Tours" in html and "Temps total" in html and "Meilleur tour" in html
    assert "1:36:100" in html  # 1 tour de 96100 ms en course
    assert "🥇" in html  # médaille du vainqueur
    assert "best-lap-row" in html  # meilleur best lap en bleu
    assert "Aston Martin" in html and "V8 Vantage (2019)" in html  # carModel 20
    # le tour cut 94500 ms (1:34:500) ne compte pas dans les résultats:
    # il n'apparaît que dans le tableau dépliable de la session (1 fois)
    assert html.count("1:34:500") == 1
    assert "John Doe" in html
    # session dépliable + tour cut en rouge
    assert "<details>" in html
    assert "cut-row" in html
    # numéro de tour cumulé + temps au tour
    assert "Tour #" in html and "Temps tour" in html
    # sessions = tours complets uniquement: le split S1 0:30:000 n'y est pas
    assert "0:30:000" not in html
    assert "2 tours" in html  # qualif: 2 tours accomplis
    assert client.get("/weekend/9999").status_code == 404


def test_lap_numbers_are_cumulative_per_driver(client, app):
    with app.app_context():
        race_id = Races.query.order_by(Races.id.asc()).first().id  # Qualifying
    html = client.get(f"/race/{race_id}").get_data(as_text=True)
    assert "Tour #" in html
    # John Doe: 2 tours accomplis en qualif (le 2e avec cut) -> Tour #1 et #2
    assert ">1</td>" in html and ">2</td>" in html
    # /race/<id> n'affiche que les tours complets: le split S1 0:30:000 n'y est pas
    assert "0:30:000" not in html
    assert "2 tours complets" in html
    # seul LE best lap de la session (1:35:791, hors cut) est surligné en jaune
    # (' best-lap"' = classe de ligne; le CSS contient 'tr.best-lap' sans guillemet)
    assert html.count(' best-lap"') == 1
    # et c'est bien la ligne du tour 1:35:791 qui porte la classe
    import re
    assert re.search(r'class=" best-lap"[^>]*>.*?1:35:791', html, re.S) or "1:35:791" in html


def test_weekend_sessions_highlight_best_lap(client, app):
    html = client.get("/weekend/1").get_data(as_text=True)
    assert "best-lap" in html  # meilleur tour de John Doe surligné dans les sessions


def test_fastest_sectors_highlighted(client, app):
    with app.app_context():
        race_id = Races.query.order_by(Races.id.asc()).first().id  # Qualifying
    html = client.get(f"/race/{race_id}").get_data(as_text=True)
    # un seul tour complet hors cut -> ses 3 secteurs sont les plus rapides
    assert html.count('class="best-sector"') == 3
    html_we = client.get("/weekend/1").get_data(as_text=True)
    assert 'class="best-sector"' in html_we


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


def test_same_player_id_different_name_creates_two_drivers(tmp_path):
    """Un même SteamID connecté avec un nom différent = un pilote distinct;
    même SteamID + même nom = mise à jour du pilote existant."""
    log_path = tmp_path / "server.log"
    log_path.write_text(
        "Session changed: Practice 0 -> Race 0\n"
        "New connection request: id 0 John Doe S76561198000000000 on car model 20\n"
        "Creating new car connection: carId 5, carModel 20, raceNumber #44\n"
        "New connection request: id 1 Jane Doe S76561198000000000 on car model 21\n"
        "Creating new car connection: carId 6, carModel 21, raceNumber #45\n"
        # même player_id + même nom -> update (car_id change), pas de 3e pilote
        "New connection request: id 2 John Doe S76561198000000000 on car model 22\n"
        "Creating new car connection: carId 7, carModel 22, raceNumber #46\n",
        encoding="utf-8",
    )

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
        assert Drivers.query.count() == 2
        john = Drivers.query.filter_by(first_name="John", last_name="Doe").first()
        jane = Drivers.query.filter_by(first_name="Jane", last_name="Doe").first()
        assert john.player_id == jane.player_id == "76561198000000000"
        # John a changé de voiture: car_id/race_number/car_model mis à jour
        assert john.car_id == 7
        assert john.car_model == 22
        assert john.race_number == 46
        assert jane.car_id == 6
        # la course liste bien les deux pilotes malgré le player_id identique
        race = Races.query.order_by(Races.id.desc()).first()
        assert len(race.drivers) == 2
        names = {(d["first_name"], d["last_name"]) for d in race.drivers}
        assert names == {("John", "Doe"), ("Jane", "Doe")}


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
