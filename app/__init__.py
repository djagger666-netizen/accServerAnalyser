import os

from flask import Flask, jsonify, render_template, request

from .car_models import car_info
from .extensions import db
from . import models  # noqa: F401  (enregistre les modèles)


def create_app(config_object=None, start_monitor=False):
    from config import Config

    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if db_uri.startswith("sqlite:///") and db_uri != "sqlite:///:memory:":
        os.makedirs(os.path.dirname(db_uri.replace("sqlite:///", "")), exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    register_routes(app)

    if start_monitor:
        from .log_monitor import LogMonitorService

        monitor = LogMonitorService(
            app, app.config["ACC_LOG_PATH"], app.config["ENTRYLIST_PATH"]
        )
        monitor.start()
        app.extensions["log_monitor"] = monitor

    return app


def ms_to_time(ms):
    """Formate des millisecondes en 'm:ss:mmm' (ex 95791 -> '1:35:791')."""
    if ms is None:
        return "-"
    minutes, rem = divmod(int(ms), 60_000)
    seconds, millis = divmod(rem, 1_000)
    return f"{minutes}:{seconds:02d}:{millis:03d}"


def annotate_lap_numbers(laps):
    """Numérote les tours accomplis (lap_time renseigné) par pilote, dans l'ordre chronologique."""
    counts = {}
    for driver, lap in laps:
        if lap.lap_time is not None:
            key = lap.player_id or f"car{lap.car_id}"
            counts[key] = counts.get(key, 0) + 1
            lap.lap_number = counts[key]
        else:
            lap.lap_number = None
    return laps


def annotate_best_laps(laps):
    """Marque LE meilleur tour de la session (hors cut): lap.is_best = True."""
    valid = [l.lap_time for _, l in laps if l.lap_time is not None and not l.hasCut]
    overall = min(valid) if valid else None
    for _, lap in laps:
        lap.is_best = (
            overall is not None
            and lap.lap_time == overall
            and not lap.hasCut
        )
    return laps


def driver_stats(player_id, car_model_fallback=None):
    """Stats d'un pilote: nb de tours accomplis, voiture préférée, piste préférée."""
    from sqlalchemy import func

    from .models import LapLive, Races

    laps = LapLive.query.filter(
        LapLive.player_id == player_id, LapLive.lap_time.isnot(None)
    ).count()
    car = (
        db.session.query(LapLive.car_model, func.count(LapLive.id))
        .filter(LapLive.player_id == player_id, LapLive.car_model.isnot(None))
        .group_by(LapLive.car_model)
        .order_by(func.count(LapLive.id).desc())
        .first()
    )
    car = car_info(car[0]) if car else car_info(car_model_fallback)
    track = (
        db.session.query(Races.piste, func.count(LapLive.id))
        .join(Races, Races.id == LapLive.race_id)
        .filter(LapLive.player_id == player_id, LapLive.lap_time.isnot(None))
        .group_by(Races.piste)
        .order_by(func.count(LapLive.id).desc())
        .first()
    )
    return {
        "laps": laps,
        "car": car,
        "track": track[0] if track else None,
    }


def annotate_sector_bests(laps):
    """Marque le secteur le plus rapide (hors cut) de la session: lap.best_s1/s2/s3."""
    bests = {"s1": None, "s2": None, "s3": None}
    for _, lap in laps:
        if lap.hasCut:
            continue
        for s in bests:
            v = getattr(lap, s)
            if v is not None and (bests[s] is None or v < bests[s]):
                bests[s] = v
    for _, lap in laps:
        lap.best_s1 = not lap.hasCut and lap.s1 is not None and lap.s1 == bests["s1"]
        lap.best_s2 = not lap.hasCut and lap.s2 is not None and lap.s2 == bests["s2"]
        lap.best_s3 = not lap.hasCut and lap.s3 is not None and lap.s3 == bests["s3"]
    return laps


def register_routes(app):
    from .models import Drivers, LapLive, Races, Server, WeekEnds

    app.add_template_filter(ms_to_time, "ms_to_time")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/races")
    def list_races():
        piste_filter = request.args.get("piste")
        month = request.args.get("month")
        year = request.args.get("year")

        query = Races.query
        if piste_filter:
            query = query.filter(Races.piste == piste_filter)
        if month and year:
            query = query.filter(db.extract("month", Races.date) == month)
            query = query.filter(db.extract("year", Races.date) == year)

        races = query.order_by(Races.date.desc()).all()
        pistes = [p[0] for p in db.session.query(Races.piste).distinct().all()]
        by_we = {}
        for r in races:
            by_we.setdefault(r.we_id, []).append(r)
        groups = [
            {"we": WeekEnds.query.get(we_id), "races": by_we[we_id]}
            for we_id in sorted(by_we, reverse=True)
        ]
        return render_template("races.html", groups=groups, pistes=pistes)

    @app.route("/weekend/<int:we_id>")
    def weekend_detail(we_id):
        we = WeekEnds.query.get_or_404(we_id)
        races = Races.query.filter_by(we_id=we_id).order_by(Races.id.asc()).all()
        sessions = []
        for race in races:
            laps = annotate_lap_numbers(
                db.session.query(Drivers, LapLive)
                .outerjoin(Drivers, LapLive.player_id == Drivers.player_id)
                .filter(LapLive.race_id == race.id)
                .order_by(LapLive.id.asc())
                .all()
            )
            completed = [(d, l) for d, l in laps if l.lap_time is not None]
            annotate_sector_bests(annotate_best_laps(completed))
            best = {}
            for driver, lap in laps:
                # résultats: on ignore les tours avec cut
                if lap.lap_time is None or lap.hasCut:
                    continue
                key = lap.player_id or f"car{lap.car_id}"
                cur = best.get(key)
                if cur is None or lap.lap_time < cur[0]:
                    best[key] = (lap.lap_time, driver)
            ranking = sorted(best.values(), key=lambda b: b[0])
            best_lap_by_key = {k: v[0] for k, v in best.items()}
            # résultat de course: plus de tours d'abord, puis moins de temps cumulé
            race_stats = {}
            for driver, lap in laps:
                if lap.lap_time is None:
                    continue
                key = lap.player_id or f"car{lap.car_id}"
                n, total, drv = race_stats.get(key, (0, 0, driver))
                race_stats[key] = (n + 1, total + lap.lap_time, drv)
            race_ranking = [
                {
                    "n": n,
                    "total": total,
                    "driver": drv,
                    "best_lap": best_lap_by_key.get(key),
                    "car": car_info(drv.car_model) if drv else None,
                }
                for key, (n, total, drv) in sorted(
                    race_stats.items(), key=lambda kv: (-kv[1][0], kv[1][1])
                )
            ]
            best_laps = [r["best_lap"] for r in race_ranking if r["best_lap"] is not None]
            sessions.append({
                "race": race,
                "laps": laps,
                "display_laps": [(d, l) for d, l in laps if l.lap_time is not None],
                "ranking": ranking,
                "race_ranking": race_ranking,
                "best_lap_overall": min(best_laps) if best_laps else None,
                "is_race": race.race_session in ("Race", "Race Completed"),
            })
        logos_dir = os.path.join(app.root_path, "static", "logos")
        available_logos = set(os.listdir(logos_dir)) if os.path.isdir(logos_dir) else set()
        return render_template(
            "weekend_detail.html", we=we, sessions=sessions, available_logos=available_logos
        )

    @app.route("/race/<int:race_id>")
    def race_detail(race_id):
        race = Races.query.get_or_404(race_id)
        results = annotate_sector_bests(annotate_best_laps(annotate_lap_numbers(
            db.session.query(Drivers, LapLive)
            .outerjoin(Drivers, LapLive.player_id == Drivers.player_id)
            .filter(LapLive.race_id == race_id, LapLive.lap_time.isnot(None))
            .order_by(LapLive.id.asc())
            .all()
        )))
        return render_template("race_detail.html", race=race, results=results)

    @app.route("/live")
    def live_page():
        return render_template("live.html")

    @app.route("/api/live_data")
    def api_live_data():
        race = Races.query.order_by(Races.id.desc()).first()
        data = {"status": "active", "race": None, "laps": []}
        if race:
            data["race"] = {
                "id": race.id,
                "piste": race.piste,
                "race_session": race.race_session,
                "date": race.date.isoformat() if race.date else None,
            }
            laps = (
                db.session.query(Drivers, LapLive)
                .outerjoin(Drivers, LapLive.player_id == Drivers.player_id)
                .filter(LapLive.race_id == race.id)
                .order_by(LapLive.id.desc())
                .limit(50)
                .all()
            )
            data["laps"] = [
                {
                    "car_id": lap.car_id,
                    "driver": driver.full_name() if driver else None,
                    "place": lap.driver_place,
                    "lap_time": lap.lap_time,
                    "s1": lap.s1,
                    "s2": lap.s2,
                    "s3": lap.s3,
                    "fuel": lap.fuel,
                    "hasCut": lap.hasCut,
                    "sessionOver": lap.sessionOver,
                }
                for driver, lap in laps
            ]
        return jsonify(data)

    @app.route("/drivers")
    def list_drivers():
        drivers = Drivers.query.order_by(Drivers.last_name.asc()).all()
        stats = {d.id: driver_stats(d.player_id, d.car_model) for d in drivers}
        return render_template("drivers.html", drivers=drivers, stats=stats)

    @app.route("/driver/<int:driver_id>")
    def driver_profile(driver_id):
        driver = Drivers.query.get_or_404(driver_id)
        participated_race_ids = (
            db.session.query(LapLive.race_id)
            .filter(LapLive.player_id == driver.player_id)
            .distinct()
            .all()
        )
        race_ids = [r[0] for r in participated_race_ids]
        races = Races.query.filter(Races.id.in_(race_ids)).all() if race_ids else []
        stats = driver_stats(driver.player_id, driver.car_model)
        return render_template(
            "driver_detail.html", driver=driver, races=races, stats=stats
        )

    @app.route("/servers")
    def list_servers():
        servers = Server.query.all()
        return render_template("servers.html", servers=servers)
