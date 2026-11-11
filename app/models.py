from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy.ext.mutable import MutableList

from .extensions import db


class Server(db.Model):
    __tablename__ = "servers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    path = db.Column(db.String(500), nullable=False)
    tcp_port = db.Column(db.Integer, nullable=False, default=9201)
    udp_port = db.Column(db.Integer, nullable=False, default=9201)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "tcp_port": self.tcp_port,
            "udp_port": self.udp_port,
        }


class Drivers(db.Model):
    __tablename__ = "drivers"
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, nullable=True)
    driver_id = db.Column(db.Integer, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    player_id = db.Column(db.String(50), nullable=False)
    car_model = db.Column(db.Integer, nullable=False)
    race_number = db.Column(db.Integer, nullable=False)

    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Races(db.Model):
    __tablename__ = "races"
    id = db.Column(db.Integer, primary_key=True)
    we_id = db.Column(db.Integer, nullable=False)
    piste = db.Column(db.String(50), nullable=False)
    race_session = db.Column(db.String(50), nullable=True)
    drivers = db.Column(MutableList.as_mutable(JSON), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class WeekEnds(db.Model):
    __tablename__ = "weekends"
    id = db.Column(db.Integer, primary_key=True)
    races_id = db.Column(MutableList.as_mutable(JSON), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class LapLive(db.Model):
    __tablename__ = "laps_live"
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.String(50), nullable=True)
    car_id = db.Column(db.Integer, nullable=False)
    car_model = db.Column(db.Integer, nullable=True)
    driver_place = db.Column(db.Integer, nullable=False)
    race_id = db.Column(db.Integer, nullable=False)
    lap_time = db.Column(db.Integer, nullable=True)
    race_session = db.Column(db.String(50), nullable=True)
    timestamp_ms = db.Column(db.Float, nullable=False)
    s1 = db.Column(db.Integer, nullable=True)
    s2 = db.Column(db.Integer, nullable=True)
    s3 = db.Column(db.Integer, nullable=True)
    fuel = db.Column(db.Float, nullable=False)
    sessionOver = db.Column(db.Boolean, nullable=False, default=False)
    hasCut = db.Column(db.Boolean, nullable=False, default=False)
