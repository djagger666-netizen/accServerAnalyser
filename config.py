import importlib.util
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOCAL_CONFIG_PATH = os.path.join(BASE_DIR, "config.local.py")


def _resolve(path):
    """Résout un chemin relatif par rapport à la racine du dépôt."""
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    return os.path.normpath(path)


def _apply_local_overrides(config_cls, path):
    """Applique les surcharges d'un fichier config.local.py (variables en MAJUSCULES)."""
    if not os.path.exists(path):
        return
    spec = importlib.util.spec_from_file_location("config_local", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in dir(mod):
        if name.isupper():
            setattr(config_cls, name, getattr(mod, name))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "laps.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Chemin du fichier server.log du serveur ACC surveillé
    # (relatif = résolu depuis la racine du dépôt, ex: ..\accweb_v1.27.0\config\1786545622\log\server.log)
    ACC_LOG_PATH = _resolve(
        os.environ.get(
            "ACC_LOG_PATH",
            os.path.join("server_files", "log", "server.log"),
        )
    )
    # Chemin de l'entrylist du serveur (correspondance numéro de course <-> pilote)
    ENTRYLIST_PATH = _resolve(
        os.environ.get(
            "ENTRYLIST_PATH",
            os.path.join("server_files", "cfg", "entrylist.json"),
        )
    )
    # Dossier contenant server.log
    ACC_LOG_DIR = _resolve(os.environ.get("ACC_LOG_DIR", os.path.dirname(ACC_LOG_PATH)))
    # Dossier des logs archivés par le serveur ACC (logs_YYYYMMDD_....log),
    # par défaut le dossier "logs" à côté du dossier "log"
    ACC_LOGS_DIR = _resolve(
        os.environ.get("ACC_LOGS_DIR", os.path.join(os.path.dirname(ACC_LOG_DIR), "logs"))
    )
    # Fichier d'état du moniteur (offsets de lecture par fichier, pour ne pas
    # relire les logs au redémarrage et suivre les fichiers archivés)
    MONITOR_STATE_PATH = _resolve(
        os.environ.get("MONITOR_STATE_PATH", os.path.join("instance", "monitor_state.json"))
    )

    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "5000"))


# Surcharge locale optionnelle via config.local.py (voir config.local.example.py)
_apply_local_overrides(Config, LOCAL_CONFIG_PATH)
for _path_attr in ("ACC_LOG_PATH", "ENTRYLIST_PATH", "ACC_LOG_DIR", "ACC_LOGS_DIR", "MONITOR_STATE_PATH"):
    setattr(Config, _path_attr, _resolve(getattr(Config, _path_attr)))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
