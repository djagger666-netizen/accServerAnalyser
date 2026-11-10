"""Requêtes utilitaires d'interrogation de la base (CLI de démonstration)."""

from sqlalchemy import func

from .extensions import db
from .models import Drivers, LapLive, Races


def print_all_races():
    """Affiche toutes les courses enregistrées."""
    print("\n=== LISTE DE TOUTES LES COURSES ===")
    races = Races.query.all()
    if not races:
        print("Aucune course trouvée dans la base.")
        return
    for r in races:
        date_str = r.date.strftime("%d/%m/%Y %H:%M") if r.date else "Inconnue"
        print(f"ID: {r.id} | Date: {date_str} | Piste: {r.piste} | Session: {r.race_session}")
    print("===================================\n")


def find_races_by_track(track_name):
    """Recherche les courses par nom de piste."""
    print(f"\n=== RECHERCHE : {track_name.upper()} ===")
    races = Races.query.filter(Races.piste.ilike(f"%{track_name}%")).all()
    for r in races:
        print(f"[{r.id}] {r.piste} ({r.date})")
    if not races:
        print("Aucune course trouvée pour cette piste.")
    print("====================================\n")


def get_race_summary(race_id):
    """Affiche le résumé d'une course et ses pilotes."""
    print(f"\n=== RÉSUMÉ DE LA COURSE ID: {race_id} ===")
    race = db.session.get(Races, race_id)
    if not race:
        print("Course introuvable.")
        return
    print(f"Piste   : {race.piste}")
    print(f"Date    : {race.date}")
    print(f"Session : {race.race_session}")
    print("\nPilotes ayant participé :")
    participants = (
        db.session.query(Drivers.first_name, Drivers.last_name)
        .join(LapLive, Drivers.player_id == LapLive.player_id)
        .filter(LapLive.race_id == race.id)
        .distinct()
        .all()
    )
    if participants:
        for i, (fname, lname) in enumerate(participants, 1):
            print(f"{i}. {fname} {lname}")
    else:
        print("Aucun pilote enregistré pour cette course.")
    print("====================================\n")


def count_races_per_track():
    """Statistiques : nombre de courses par piste."""
    print("\n=== STATISTIQUES : COURSES PAR PISTE ===")
    stats = db.session.query(Races.piste, func.count(Races.id)).group_by(Races.piste).all()
    for piste, count in stats:
        print(f"{piste:20} : {count} course(s)")
    print("======================================\n")


def main():
    print_all_races()
    find_races_by_track("Spa")
    get_race_summary(1)
    count_races_per_track()


if __name__ == "__main__":
    from . import create_app

    app = create_app()
    with app.app_context():
        main()
