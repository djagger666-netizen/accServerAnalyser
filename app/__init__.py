import os

from flask import Flask, jsonify, render_template, request

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


def register_routes(app):
    from .models import Drivers, LapLive, Races, Server

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
        return render_template("races.html", races=races, pistes=pistes)

    @app.route("/race/<int:race_id>")
    def race_detail(race_id):
        race = Races.query.get_or_404(race_id)
        results = (
            db.session.query(Drivers, LapLive)
            .outerjoin(Drivers, LapLive.player_id == Drivers.player_id)
            .filter(LapLive.race_id == race_id)
            .order_by(LapLive.lap_time.asc())
            .all()
        )
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
        return render_template("drivers.html", drivers=drivers)

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
        return render_template("driver_detail.html", driver=driver, races=races)

    @app.route("/servers")
    def list_servers():
        servers = Server.query.all()
        return render_template("servers.html", servers=servers)
