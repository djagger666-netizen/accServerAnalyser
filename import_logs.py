"""Scanne un dossier de logs et importe tous les fichiers trouvés dans la base.

Usage :
    python import_logs.py "..\\accweb_v1.27.0\\config\\1786545622\\logs"
    python import_logs.py <dossier> --pattern "logs_*.log"

Les fichiers déjà lus (état persisté dans instance/monitor_state.json) ne sont
pas réimportés : on peut relancer la commande sans créer de doublons.
"""

import argparse
import glob
import os
import sys

from app import create_app
from app.log_monitor import LogMonitorService
from app.models import Drivers, LapLive, Races, WeekEnds


def main():
    parser = argparse.ArgumentParser(description="Importe un dossier de logs ACC dans la base.")
    parser.add_argument("logs_dir", help="dossier contenant les fichiers .log")
    parser.add_argument("--pattern", default="*.log", help="pattern des fichiers (défaut: *.log)")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.logs_dir, args.pattern)))
    if not files:
        print(f"Aucun fichier trouvé dans {args.logs_dir} avec le pattern {args.pattern}")
        return 1

    app = create_app(start_monitor=False)
    monitor = LogMonitorService(
        app, app.config["ACC_LOG_PATH"], app.config["ENTRYLIST_PATH"]
    )
    print(f"{len(files)} fichier(s) à scanner dans {args.logs_dir}")
    with app.app_context():
        for path in files:
            before = LapLive.query.count()
            monitor.tail_file(path)
            print(f"  {os.path.basename(path)}: +{LapLive.query.count() - before} lignes")
        print("\n=== Bilan base ===")
        print(f"week-ends: {WeekEnds.query.count()} | courses: {Races.query.count()} | "
              f"pilotes: {Drivers.query.count()} | tours+splits: {LapLive.query.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
