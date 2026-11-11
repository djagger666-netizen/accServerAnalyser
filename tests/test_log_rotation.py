import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime

from app import create_app
from app.log_monitor import LogMonitorService, log_sort_key
from app.models import LapLive, Races, WeekEnds

LINE_TRACK = "Track spa was set and updated\n"
LINE_LAP = ("Lap carId 5, driverId 1, lapTime 1:35:791, timestampMS 35791.000000, "
            "flags: 0, fuel 45.2\n")


@pytest.fixture()
def env(tmp_path):
    log = tmp_path / "log" / "server.log"
    log.parent.mkdir()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    class TestCfg:
        SECRET_KEY = "test"
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "test.db")
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        ACC_LOG_PATH = str(log)
        ACC_LOGS_DIR = str(logs_dir)
        ENTRYLIST_PATH = str(tmp_path / "entrylist.json")
        MONITOR_STATE_PATH = str(tmp_path / "monitor_state.json")
        HOST = "127.0.0.1"
        PORT = 5000

    app = create_app(TestCfg, start_monitor=False)
    return app, log, logs_dir, tmp_path


def make_monitor(app, log, tmp_path):
    return LogMonitorService(app, str(log), "unused.json",
                             state_path=str(tmp_path / "monitor_state.json"))


def test_new_lines_are_read_only_once(env):
    app, log, logs_dir, tmp_path = env
    log.write_text(LINE_TRACK + LINE_LAP, encoding="utf-8")
    m = make_monitor(app, log, tmp_path)
    with app.app_context():
        m.tail_file(str(log))
        m.tail_file(str(log))  # second passage: rien de nouveau
        assert LapLive.query.count() == 1
        with open(str(log), "a", encoding="utf-8") as f:
            f.write(LINE_LAP)
        m.tail_file(str(log))
        assert LapLive.query.count() == 2


def test_truncated_file_is_reread_from_start(env):
    app, log, logs_dir, tmp_path = env
    log.write_text(LINE_TRACK + LINE_LAP + LINE_LAP, encoding="utf-8")
    m = make_monitor(app, log, tmp_path)
    with app.app_context():
        m.tail_file(str(log))
        assert LapLive.query.count() == 2
        # le serveur recrée un server.log plus petit
        log.write_text(LINE_TRACK + LINE_LAP, encoding="utf-8")
        m.tail_file(str(log))
        assert LapLive.query.count() == 3  # relu depuis le début


def test_partial_line_is_processed_like_initial_logic(env):
    # logique initiale: readlines traite la dernière ligne même sans \n final
    app, log, logs_dir, tmp_path = env
    log.write_text(LINE_TRACK + LINE_LAP.rstrip("\n"), encoding="utf-8")
    m = make_monitor(app, log, tmp_path)
    with app.app_context():
        m.tail_file(str(log))
        assert LapLive.query.count() == 1


def test_archived_logs_are_replayed(env):
    app, log, logs_dir, tmp_path = env
    archive = logs_dir / "logs_20260824_181416_1786545622.log"
    archive.write_text(LINE_TRACK + "Session changed: Practice -> Race 0\n" + LINE_LAP,
                       encoding="utf-8")
    log.write_text("", encoding="utf-8")
    m = make_monitor(app, log, tmp_path)
    m.logs_dir = str(logs_dir)
    with app.app_context():
        m.replay_archived_logs()
        assert Races.query.count() == 1
        assert LapLive.query.count() == 1
        # rejouer ne duplique rien (offset persisté)
        m.replay_archived_logs()
        assert LapLive.query.count() == 1


def test_consecutive_weekend_resets_reuse_empty_weekend(env):
    app, log, logs_dir, tmp_path = env
    log.write_text(
        "Resetting race weekend\n"
        "Resetting race weekend\n"
        "Session changed: Practice -> Practice 0\n"
        "Resetting race weekend\n"
        "Session changed: Practice -> Qualifying 0\n",
        encoding="utf-8",
    )
    m = make_monitor(app, log, tmp_path)
    with app.app_context():
        m.tail_file(str(log))
        # 2 resets consécutifs -> même week-end (le n°1, créé à l'init);
        # le reset après une course -> nouveau week-end
        assert WeekEnds.query.count() == 2
        races = Races.query.order_by(Races.id).all()
        assert [r.we_id for r in races] == [1, 2]


def test_archived_files_sorted_by_embedded_date(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    for name in ("zz-logs_20260910_183152_1.log", "aa-logs_20260812_165000_1.log",
                 "mm-logs_20260824_181416_1.log"):
        (logs_dir / name).write_text("", encoding="utf-8")
    files = sorted((p.name for p in logs_dir.iterdir()), key=log_sort_key)
    assert files == [
        "aa-logs_20260812_165000_1.log",
        "mm-logs_20260824_181416_1.log",
        "zz-logs_20260910_183152_1.log",
    ]


def test_practice_session_starts_new_weekend(env):
    # règle: "-> Practice 0" = début d'un nouveau week-end, même sans
    # "Resetting race weekend" explicite dans le log
    app, log, logs_dir, tmp_path = env
    log.write_text(
        "Session changed: Practice -> Race 0\n" + LINE_LAP +
        "Session changed: Race -> Practice 0\n" +
        "Session changed: Practice -> Qualifying 0\n",
        encoding="utf-8",
    )
    m = make_monitor(app, log, tmp_path)
    with app.app_context():
        m.tail_file(str(log))
        assert WeekEnds.query.count() == 2
        races = Races.query.order_by(Races.id).all()
        assert [r.race_session for r in races] == ["Race", "Practice", "Qualifying"]
        assert [r.we_id for r in races] == [1, 2, 2]


def test_consecutive_practice_stays_same_weekend(env):
    app, log, logs_dir, tmp_path = env
    log.write_text(
        "Session changed: Race -> Practice 0\n"
        "Session changed: Race -> Practice 0\n",  # ligne doublée (restart serveur)
        encoding="utf-8",
    )
    m = make_monitor(app, log, tmp_path)
    with app.app_context():
        m.tail_file(str(log))
        assert WeekEnds.query.count() == 1
        assert Races.query.count() == 2
        assert all(r.we_id == 1 for r in Races.query.all())


def test_line_date_prefix_used_for_archived_logs(env):
    # la date enregistrée vient du préfixe ISO en début de ligne
    app, log, logs_dir, tmp_path = env
    archive = logs_dir / "logs_20260824_181416_1786545622.log"
    archive.write_text(
        "2026-08-24T18:14:16.123Z: Session changed: Practice -> Race 0\n"
        "2026-08-24T18:20:00.000Z: " + LINE_LAP,
        encoding="utf-8",
    )
    m = make_monitor(app, log, tmp_path)
    m.logs_dir = str(logs_dir)
    with app.app_context():
        m.replay_archived_logs()
        lap = LapLive.query.first()
        race = Races.query.first()
        assert lap.date == datetime(2026, 8, 24, 18, 20, 0)
        assert race.date == datetime(2026, 8, 24, 18, 14, 16, 123000)
    # server.log live (préfixe en ms, pas de date ISO): date None
    log.write_text(LINE_LAP, encoding="utf-8")
    with app.app_context():
        m.tail_file(str(log))
        assert LapLive.query.order_by(LapLive.id.desc()).first().date is None


def test_restart_does_not_create_empty_weekend(env):
    app, log, logs_dir, tmp_path = env
    log.write_text("Session changed: Practice -> Race 0\n" + LINE_LAP, encoding="utf-8")
    with app.app_context():
        make_monitor(app, log, tmp_path).tail_file(str(log))
        n_we = WeekEnds.query.count()
        # redémarrage de l'appli (nouveau moniteur): aucun week-end vide ajouté
        m2 = make_monitor(app, log, tmp_path)
        assert WeekEnds.query.count() == n_we
        assert m2.we_id == WeekEnds.query.order_by(WeekEnds.id.desc()).first().id


def test_piste_persisted_across_monitor_instances(env):
    app, log, logs_dir, tmp_path = env
    log.write_text(LINE_TRACK + LINE_LAP, encoding="utf-8")
    with app.app_context():
        make_monitor(app, log, tmp_path).tail_file(str(log))
        # redémarrage: la piste doit être restaurée depuis le fichier d'état
        m2 = make_monitor(app, log, tmp_path)
        assert m2.piste == "spa"


def test_state_persisted_across_monitor_instances(env):
    app, log, logs_dir, tmp_path = env
    log.write_text(LINE_TRACK + LINE_LAP, encoding="utf-8")
    with app.app_context():
        make_monitor(app, log, tmp_path).tail_file(str(log))
        assert LapLive.query.count() == 1
        # nouveau moniteur (redémarrage de l'appli), même fichier d'état
        m2 = make_monitor(app, log, tmp_path)
        m2.tail_file(str(log))
        assert LapLive.query.count() == 1  # pas de relecture
