"""Correspondance carModel (id du server.log ACC) -> (marque, modèle).

Table issue du ACC Server Admin Handbook 1.10.2 (appendice "Car model list").
"""

from collections import namedtuple

CarInfo = namedtuple("CarInfo", ["brand", "model", "color"])

BRAND_COLORS = {
    "Porsche": "#d5001c",
    "Mercedes-AMG": "#00a3e0",
    "Ferrari": "#ff2800",
    "Audi": "#bb0a30",
    "Lamborghini": "#00a651",
    "McLaren": "#ff8000",
    "Nissan": "#c3002f",
    "BMW": "#0066b1",
    "Bentley": "#00594c",
    "Aston Martin": "#006f62",
    "Jaguar": "#444444",
    "Lexus": "#b00d20",
    "Honda": "#e40521",
    "Ford": "#003478",
    "Alpine": "#0057b8",
    "Chevrolet": "#cd9834",
    "Ginetta": "#e30613",
    "KTM": "#ff6600",
    "Maserati": "#0c2340",
}

CAR_MODELS = {
    0: ("Porsche", "991 GT3 R"),
    1: ("Mercedes-AMG", "GT3"),
    2: ("Ferrari", "488 GT3"),
    3: ("Audi", "R8 LMS"),
    4: ("Lamborghini", "Huracán GT3"),
    5: ("McLaren", "650S GT3"),
    6: ("Nissan", "GT-R Nismo GT3 2018"),
    7: ("BMW", "M6 GT3"),
    8: ("Bentley", "Continental GT3 2018"),
    9: ("Porsche", "991II GT3 Cup"),
    10: ("Nissan", "GT-R Nismo GT3 2017"),
    11: ("Bentley", "Continental GT3 2016"),
    12: ("Aston Martin", "V12 Vantage GT3"),
    13: ("Lamborghini", "Gallardo R-EX"),
    14: ("Jaguar", "G3"),
    15: ("Lexus", "RC F GT3"),
    16: ("Lamborghini", "Huracán Evo (2019)"),
    17: ("Honda", "NSX GT3"),
    18: ("Lamborghini", "Huracán SuperTrofeo"),
    19: ("Audi", "R8 LMS Evo (2019)"),
    20: ("Aston Martin", "V8 Vantage (2019)"),
    21: ("Honda", "NSX Evo (2019)"),
    22: ("McLaren", "720S GT3 (2019)"),
    23: ("Porsche", "911II GT3 R (2019)"),
    24: ("Ferrari", "488 GT3 Evo 2020"),
    25: ("Mercedes-AMG", "GT3 2020"),
    26: ("Ferrari", "488 Challenge Evo"),
    27: ("BMW", "M2 CS Racing"),
    28: ("Porsche", "911 GT3 Cup (Type 992)"),
    29: ("Lamborghini", "Huracán Super Trofeo EVO2"),
    30: ("BMW", "M4 GT3"),
    31: ("Audi", "R8 LMS GT3 evo II"),
    32: ("Ferrari", "296 GT3"),
    33: ("Lamborghini", "Huracán Evo2"),
    34: ("Porsche", "992 GT3 R"),
    35: ("McLaren", "720S GT3 Evo 2023"),
    36: ("Ford", "Mustang GT3"),
    50: ("Alpine", "A110 GT4"),
    51: ("Aston Martin", "V8 Vantage GT4"),
    52: ("Audi", "R8 LMS GT4"),
    53: ("BMW", "M4 GT4"),
    55: ("Chevrolet", "Camaro GT4"),
    56: ("Ginetta", "G55 GT4"),
    57: ("KTM", "X-Bow GT4"),
    58: ("Maserati", "MC GT4"),
    59: ("McLaren", "570S GT4"),
    60: ("Mercedes-AMG", "GT4"),
    61: ("Porsche", "718 Cayman GT4"),
    80: ("Audi", "R8 LMS GT2"),
    82: ("KTM", "X-BOW GT2"),
    83: ("Maserati", "MC20 GT2"),
    84: ("Mercedes-AMG", "GT2"),
    85: ("Porsche", "911 GT2 RS CS Evo"),
    86: ("Porsche", "935"),
}


def car_info(car_model_id):
    """Retourne un CarInfo(brand, model, color) pour un id carModel ACC."""
    if car_model_id is None:
        return None
    brand, model = CAR_MODELS.get(int(car_model_id), ("?", f"carModel {car_model_id}"))
    return CarInfo(brand, model, BRAND_COLORS.get(brand, "#555555"))
