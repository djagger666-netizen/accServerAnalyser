import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

LINE = ("Lap carId 5, driverId 1, lapTime 1:35:791, timestampMS 35791.0, "
        "flags: 0, fuel 45.2\n")


def test_import_logs_scans_directory(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "logs_20260824_181416_1.log").write_text("Track spa was set and updated\n" + LINE, encoding="utf-8")
    (logs_dir / "logs_20260825_101010_2.log").write_text(LINE, encoding="utf-8")
    db = tmp_path / "import.db"
    state = tmp_path / "state.json"

    env = dict(os.environ)
    env["DATABASE_URL"] = "sqlite:///" + str(db)
    env["ACC_LOG_PATH"] = str(tmp_path / "server.log")
    env["ENTRYLIST_PATH"] = str(tmp_path / "entrylist.json")
    env["MONITOR_STATE_PATH"] = str(state)

    # 1er passage : 2 fichiers importés
    r = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "import_logs.py"), str(logs_dir)],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "2 fichier(s)" in r.stdout
    assert "tours+splits: 2" in r.stdout

    # 2e passage : aucun doublon (état persisté)
    r2 = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "import_logs.py"), str(logs_dir)],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env,
    )
    assert r2.returncode == 0, r2.stderr
    assert "tours+splits: 2" in r2.stdout


def test_import_logs_empty_directory(tmp_path):
    env = dict(os.environ)
    env["DATABASE_URL"] = "sqlite:///" + str(tmp_path / "import.db")
    env["ACC_LOG_PATH"] = str(tmp_path / "server.log")
    env["ENTRYLIST_PATH"] = str(tmp_path / "entrylist.json")
    env["MONITOR_STATE_PATH"] = str(tmp_path / "state.json")
    r = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "import_logs.py"), str(tmp_path / "vide")],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env,
    )
    assert r.returncode == 1
    assert "Aucun fichier" in r.stdout
