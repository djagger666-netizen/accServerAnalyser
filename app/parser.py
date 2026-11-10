import re

# Ligne de tour du server.log ACC, ex :
#  carId 5, driverId 1, lapTime 1:35.791, timestampMS 35791.647, flags: 0,
#  S1 30.123, S2 32.456, S3 33.212, fuel 45.2, hasCut
LAP_REGEX = re.compile(
    r" carId (?P<car_id>\d+), "
    r"driverId (?P<driver_place>\d+), "
    r"lapTime (?P<lap_time>[^,]+), "
    r"timestampMS (?P<timestamp_ms>[\d.]+), "
    r"flags: (?P<flag>[^,]+), "
    r"(?:S1 (?P<s1>[^,]+), )?"
    r"(?:S2 (?P<s2>[^,]+), )?"
    r"(?:S3 (?P<s3>[^,]+), )?"
    r"fuel (?P<fuel>[\d.]+)"
    r"(?:, (?P<info1>.*))?"
    r"(?:, (?P<info2>.*))?"
    r"(?:, (?P<info3>.*))?"
)

# ex : New connection request: id 0 Joe  Siffert S76561198000653331 on car model 22
DRIVER_REQUEST_REGEX = re.compile(
    r"connection request: id (?P<driver_id>\d+)[ ,]+"
    r"(?P<first_name>.+?)[ ,]+"
    r"(?P<last_name>.+?)[ ,]+"
    r"S(?P<player_id>[^ ,]+)[ ,]+"
    r"on car model (?P<car_model>\d+)"
)

# ex : Recognized reconnect: carId5, carModel 20, raceNumber #44
RECONNECT_REGEX = re.compile(
    r"Recognized reconnect: carId(?P<car_id>\d+)"
    r", carModel (?P<car_model>\d+)"
    r", raceNumber #(?P<race_number>\d+)"
)

# ex : Creating new car connection: carId 5, carModel 20, raceNumber #44
NEW_CAR_REGEX = re.compile(
    r"Creating new car connection: carId (?P<car_id>\d+)"
    r", carModel (?P<car_model>\d+)"
    r", raceNumber #(?P<race_number>\d+)"
)

# ex : Track monza was set and updated
TRACK_REGEX = re.compile(r"Track (?P<piste>[^,]+) was set")

INT32_MAX_MS = 2147483647


def time_to_ms(value):
    """Convertit un temps du log ('m:ss:mmm', ex '1:35:791') en millisecondes.

    Retourne None pour le sentinel 2147483647 (tour/secteur invalide).
    """
    if value is None:
        return None
    parts = [p for p in str(value).strip().split(":") if p != ""]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        try:
            ms = int(round(float(str(value).strip()) * 1000))
            return None if ms == INT32_MAX_MS else ms
        except ValueError:
            return None
    if len(nums) == 3:
        ms = nums[0] * 60_000 + nums[1] * 1_000 + nums[2]
    elif len(nums) == 2:
        ms = nums[0] * 1_000 + nums[1]
    else:
        return None
    if ms == INT32_MAX_MS:
        return None
    return ms


def lap_time_to_ms(lap_time):
    """Convertit un temps de tour 'm:ss:mmm' en millisecondes."""
    return time_to_ms(lap_time)


def sector_to_ms(sector):
    """Convertit un secteur 'm:ss:mmm' en millisecondes."""
    return time_to_ms(sector)


def parse_lap_line(line):
    """Parse une ligne de tour ou de passage de secteur.

    Retourne un dict, ou None si la ligne ne correspond pas.
    Si lapTime est le sentinel 35791:23:647, il s'agit d'un passage de secteur
    en cours de tour : lap_time vaut None mais les secteurs (S1/S2/S3) sont conservés.
    """
    match = LAP_REGEX.search(line)
    if not match:
        return None
    data = match.groupdict()
    lap_time = lap_time_to_ms(data["lap_time"])
    has_cut = False
    session_over = False
    for info in (data["info1"], data["info2"], data["info3"]):
        if info is None:
            continue
        if "hasCut" in info:
            has_cut = True
        if "SessionOver" in info:
            session_over = True
    return {
        "car_id": int(data["car_id"]),
        "driver_place": int(data["driver_place"]),
        "lap_time": lap_time,
        "timestamp_ms": float(data["timestamp_ms"]),
        "s1": sector_to_ms(data["s1"]),
        "s2": sector_to_ms(data["s2"]),
        "s3": sector_to_ms(data["s3"]),
        "fuel": float(data["fuel"]),
        "hasCut": has_cut,
        "sessionOver": session_over,
    }


def parse_driver_request(line):
    match = DRIVER_REQUEST_REGEX.search(line)
    return match.groupdict() if match else None


def parse_car_connection(line):
    for regex in (RECONNECT_REGEX, NEW_CAR_REGEX):
        match = regex.search(line)
        if match:
            return match.groupdict()
    return None


def parse_track_line(line):
    match = TRACK_REGEX.search(line)
    return match.groupdict()["piste"] if match else None


def parse_session_change(line):
    """Retourne 'Practice', 'Qualifying' ou 'Race' selon la session atteinte, sinon None."""
    for session, marker in (
        ("Practice", " -> Practice 0"),
        ("Qualifying", " -> Qualifying 0"),
        ("Race", " -> Race 0"),
    ):
        if marker in line:
            return session
    return None
