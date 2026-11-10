from app.parser import (
    lap_time_to_ms,
    parse_car_connection,
    parse_driver_request,
    parse_lap_line,
    parse_session_change,
    parse_track_line,
    sector_to_ms,
)


def test_lap_time_to_ms():
    assert lap_time_to_ms("1:35:791") == 95791
    assert lap_time_to_ms("0:59:001") == 59001
    assert lap_time_to_ms("2:00:000") == 120000


def test_lap_time_to_ms_invalid_sentinel():
    # 2147483647 ms (int32 max) = "35791:23:647" -> tour invalide
    assert lap_time_to_ms("35791:23:647") is None
    assert lap_time_to_ms("pas un temps") is None


def test_sector_to_ms():
    assert sector_to_ms("0:30:123") == 30123
    assert sector_to_ms("1:04:522") == 64522
    assert sector_to_ms(None) is None
    assert sector_to_ms("35791:23:647") is None


def test_parse_lap_line_full():
    line = ("Lap carId 1001, driverId 0, lapTime 2:38:561, timestampMS 71778881.000000, "
            "flags: 169908633612, S1 0:55:906, S2 1:04:522, S3 0:38:132, "
            "fuel 46.000000, InLap , OutLap ")
    data = parse_lap_line(line)
    assert data["car_id"] == 1001
    assert data["driver_place"] == 0
    assert data["lap_time"] == 158561
    assert data["timestamp_ms"] == 71778881.0
    assert data["s1"] == 55906
    assert data["s2"] == 64522
    assert data["s3"] == 38132
    assert data["fuel"] == 46.0
    assert data["hasCut"] is False
    assert data["sessionOver"] is False


def test_parse_lap_line_with_flags():
    line = ("Lap carId 1004, driverId 0, lapTime 7:53:986, timestampMS 72107799.000000, "
            "flags: 16990863365, S1 6:09:771, S2 1:06:135, S3 0:38:080, "
            "fuel 58.000000, hasCut , OutLap ")
    data = parse_lap_line(line)
    assert data["hasCut"] is True
    assert data["lap_time"] == 473986

    line2 = ("Lap carId 1003, driverId 0, lapTime 2:22:335, timestampMS 72240252.000000, "
             "flags: 16990863361025, S1 0:41:917, S2 1:02:995, S3 0:37:422, "
             "fuel 28.000000, hasCut , SessionOver")
    data2 = parse_lap_line(line2)
    assert data2["hasCut"] is True
    assert data2["sessionOver"] is True


def test_parse_lap_line_sentinel_is_sector_passage():
    # ligne de passage de secteur : lapTime sentinel -> lap_time None, secteurs conservés
    line = ("Lap carId 1001, driverId 0, lapTime 35791:23:647, timestampMS 71676231.000000, "
            "flags: 169908633612, S1 0:55:906, fuel 0.000000, InLap , OutLap ")
    data = parse_lap_line(line)
    assert data is not None
    assert data["lap_time"] is None
    assert data["s1"] == 55906
    assert data["car_id"] == 1001


def test_parse_lap_line_not_a_lap():
    assert parse_lap_line("Session changed: Practice 0 -> Race 0") is None


def test_parse_driver_request():
    line = "New connection request: id 0 Joe  Siffert S76561198000653331 on car model 22"
    data = parse_driver_request(line)
    assert data["driver_id"] == "0"
    assert data["first_name"].strip() == "Joe"
    assert data["last_name"].strip() == "Siffert"
    assert data["player_id"] == "76561198000653331"
    assert data["car_model"] == "22"


def test_parse_car_connection():
    line = "Creating new car connection: carId 1001, carModel 22, raceNumber #999"
    data = parse_car_connection(line)
    assert data == {"car_id": "1001", "car_model": "22", "race_number": "999"}

    line2 = "Recognized reconnect: carId7, carModel 12, raceNumber #8"
    data2 = parse_car_connection(line2)
    assert data2["car_id"] == "7"
    assert data2["race_number"] == "8"


def test_parse_track_line():
    assert parse_track_line("Track spa was set and updated") == "spa"
    assert parse_track_line("Session changed: Race 0 -> Practice 0") is None


def test_parse_session_change():
    assert parse_session_change("Session changed: Practice 0 -> Qualifying 0") == "Qualifying"
    assert parse_session_change("Session changed: Qualifying -> Race 0") == "Race"
    assert parse_session_change("Session changed: Race 0 -> Practice 0") == "Practice"
    assert parse_session_change("Session changed: something else") is None
