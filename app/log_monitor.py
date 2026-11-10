import glob
import json
import os
import threading
import time

from .extensions import db
from .models import Drivers, LapLive, Races, WeekEnds
from .parser import (
    parse_car_connection,
    parse_driver_request,
    parse_lap_line,
    parse_session_change,
    parse_track_line,
)


class LogMonitorService(threading.Thread):
    """Surveille le server.log d'un serveur ACC et alimente la base de données."""

    def __init__(self, app, log_path, entrylist_path, state_path=None):
        super().__init__()
        self.app = app
        self.log_path = log_path
        self.entrylist_path = entrylist_path
        self.logs_dir = app.config.get("ACC_LOGS_DIR")
        self.state_path = (
            state_path
            or app.config.get("MONITOR_STATE_PATH")
            or os.path.join("instance", "monitor_state.json")
        )
        self.daemon = True
        self.running = True
        self.car_to_driver_map = {}
        self._state = {}
        self.load_state()

        self.race_id = None
        self.piste = None
        self.race_session = None
        self.we_id = None
        self.pending_driver_request = None

        self.we_id = self.commit_new_weekend()

    def load_mapping(self):
        """Charge la correspondance numéro de course -> SteamID depuis l'entrylist."""
        if not os.path.exists(self.entrylist_path):
            return
        with open(self.entrylist_path, "rb") as f:
            raw = f.read()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16")
        elif raw.startswith(b"\xef\xbb\xbf"):
            text = raw.decode("utf-8-sig")
        else:
            text = raw.decode("utf-8")
        data = json.loads(text)
        for entry in data.get("entries", []):
            race_num = entry.get("raceNumber")
            if race_num and entry.get("drivers"):
                driver_info = entry["drivers"][0]
                steam_id = (
                    driver_info.get("playerId")
                    or driver_info.get("playerID")
                    or driver_info.get("player_id")
                )
                self.car_to_driver_map[race_num] = {
                    "steam_id": steam_id,
                    "short_name": driver_info.get("shortName", "??"),
                }

    def load_state(self):
        """Charge les offsets de lecture persistés (fichier -> offset en octets)."""
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                self._state = json.load(f).get("files", {})
        except (OSError, ValueError):
            self._state = {}

    def save_state(self):
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"files": self._state}, f)
        os.replace(tmp, self.state_path)

    def archived_log_files(self):
        """Retourne les logs archivés du serveur (logs_*.log), triés par nom."""
        if not self.logs_dir or not os.path.isdir(self.logs_dir):
            return []
        return sorted(glob.glob(os.path.join(self.logs_dir, "logs_*.log")))

    def replay_archived_logs(self):
        """Rejoue les logs archivés (au démarrage ou nouveaux fichiers)."""
        for path in self.archived_log_files():
            self.tail_file(path)

    def run(self):
        try:
            self.load_mapping()
        except Exception as e:
            print(f"Entrylist illisible ({self.entrylist_path}), mapping ignoré: {e}")
        self.replay_archived_logs()
        print(f"Monitoring active on {self.log_path}")
        while self.running:
            self.tail_file(self.log_path)
            self.replay_archived_logs()
            time.sleep(1)

    def stop(self):
        self.running = False

    def tail_file(self, path):
        """Lit les nouveaux octets du fichier log depuis le dernier offset connu.

        - offset persisté par fichier dans le fichier d'état (pas de relecture
          au redémarrage de l'appli)
        - si le fichier a rétréci (tronqué/recréé), on repart de 0
        - une dernière ligne sans retour à la ligne est considérée comme
          incomplète et traitée au passage suivant
        """
        try:
            offset = int(self._state.get(path, 0))
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size < offset:
                    offset = 0
                f.seek(offset)
                data = f.read()
            new_offset = offset + len(data)
            if data and not data.endswith(b"\n"):
                idx = data.rfind(b"\n")
                if idx == -1:
                    return
                data = data[:idx]
                new_offset = offset + idx + 1
            for line in data.decode("utf-8", errors="ignore").splitlines():
                self.dispatch_line(line)
            self._state[path] = new_offset
            self.save_state()
        except Exception as e:
            print(f"Erreur lecture log {path}: {e}")

    def dispatch_line(self, line):
        if " in the future:" in line:
            return
        if "carId" in line and "lapTime" in line:
            self.process_line_new_time(line)
        elif "New connection request: " in line:
            self.process_line_driver_request(line)
        elif "Creating new car connection:" in line or "Recognized reconnect: " in line:
            self.process_line_car_connection(line)
        elif "Track " in line and " was set and updated" in line:
            self.process_line_new_piste(line)
        elif "Session changed: " in line:
            self.process_line_session_changed(line)
        elif "Resetting race weekend" in line:
            self.process_line_new_we()
        elif "-> <session completed>" in line:
            self.process_line_session_end(line)

    def commit_new_weekend(self):
        with self.app.app_context():
            we = WeekEnds(races_id=[])
            db.session.add(we)
            db.session.commit()
            we_id = we.id
            print(f"New weekend committed with ID: {we_id}")
        return we_id

    def process_line_new_piste(self, line):
        piste = parse_track_line(line)
        if piste:
            self.piste = piste
            print(f"--> Piste : {self.piste}")

    def process_line_session_end(self, line):
        if "<session completed> (Race)" in line:
            print(">> END RACE ------------------")
            with self.app.app_context():
                race = Races.query.order_by(Races.id.desc()).first()
                if race:
                    race.race_session = "Race Completed"
                    self.race_session = "Race Completed"
                    db.session.commit()
                    print(f"race_session '{self.race_session}' de la course {race.id} a jour")
        else:
            print(">> session End --------------------------------------")
            self.race_session = None

    def process_line_new_we(self):
        self.we_id = self.commit_new_weekend()

    def process_line_session_changed(self, line):
        session = parse_session_change(line)
        if not session:
            return
        print(f"--> Session : {session}")
        with self.app.app_context():
            race = Races(
                piste=self.piste or "unknown",
                we_id=self.we_id,
                race_session=session,
            )
            self.race_session = session
            db.session.add(race)
            db.session.commit()
            self.race_id = race.id
            print(f"!!! nouvelle course id={self.race_id}")

            we = WeekEnds.query.order_by(WeekEnds.id.desc()).first()
            if we is not None:
                races_id = we.races_id or []
                races_id.append(self.race_id)
                we.races_id = races_id
                db.session.commit()
                print(f"we.races_id {we.races_id} du weekend {we.id} a jour")

    def process_line_driver_request(self, line):
        data = parse_driver_request(line)
        if data:
            self.pending_driver_request = data

    def process_line_car_connection(self, line):
        data = parse_car_connection(line)
        if data is None:
            return
        if self.pending_driver_request:
            data.update(self.pending_driver_request)
            self.pending_driver_request = None
        if "player_id" not in data:
            return
        with self.app.app_context():
            driver = Drivers.query.filter_by(player_id=data["player_id"]).first()
            if driver:
                print(f"   >>> MAJ {driver.full_name()}")
                driver.first_name = data["first_name"]
                driver.last_name = data["last_name"]
                driver.player_id = data["player_id"]
                driver.car_model = int(data["car_model"])
                driver.race_number = int(data["race_number"])
                driver.car_id = int(data["car_id"])
            else:
                print(f"   >>> New {data['first_name']} {data['last_name']}")
                driver = Drivers(
                    driver_id=int(data["driver_id"]),
                    player_id=data["player_id"],
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    car_model=int(data["car_model"]),
                    race_number=int(data["race_number"]),
                    car_id=int(data["car_id"]),
                )
            db.session.add(driver)
            db.session.commit()

            race = Races.query.order_by(Races.id.desc()).first()
            if race:
                drivers = race.drivers or []
                new_driver = {"player_id": data["player_id"], "driver_id": int(data["driver_id"])}
                if not any(d.get("player_id") == new_driver["player_id"] for d in drivers):
                    drivers.append(new_driver)
                    race.drivers = drivers
                    db.session.commit()

    def process_line_new_time(self, line):
        data = parse_lap_line(line)
        if data is None:
            return
        kind = "tour" if data["lap_time"] is not None else "secteur"
        print(f"      newTime[{kind}]: car={data['car_id']} race={self.race_id} "
              f"lap={data['lap_time']}ms cut={data['hasCut']} over={data['sessionOver']}")
        with self.app.app_context():
            driver = Drivers.query.filter_by(car_id=data["car_id"]).first()
            lap = LapLive(
                car_id=data["car_id"],
                race_id=self.race_id or 0,
                race_session=self.race_session,
                driver_place=data["driver_place"],
                player_id=driver.player_id if driver else None,
                lap_time=data["lap_time"],
                timestamp_ms=data["timestamp_ms"],
                s1=data["s1"],
                s2=data["s2"],
                s3=data["s3"],
                fuel=data["fuel"],
                hasCut=data["hasCut"],
                sessionOver=data["sessionOver"],
            )
            db.session.add(lap)
            db.session.commit()
