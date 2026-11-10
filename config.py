import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "laps.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Chemin du fichier server.log du serveur ACC surveillé
    ACC_LOG_PATH = os.environ.get(
        "ACC_LOG_PATH",
        os.path.join(BASE_DIR, "server_files", "log", "server.log"),
    )
    # Chemin de l'entrylist du serveur (correspondance numéro de course <-> pilote)
    ENTRYLIST_PATH = os.environ.get(
        "ENTRYLIST_PATH",
        os.path.join(BASE_DIR, "server_files", "cfg", "entrylist.json"),
    )

    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "5000"))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
