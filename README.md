# ACC Server Analyser

Application web Flask qui surveille le fichier `server.log` d'un serveur
**Assetto Corsa Competizione** et en fait un résumé / historique de la vie du
serveur : week-ends, sessions (Practice / Qualifying / Race), pistes, pilotes
connectés et tours réalisés (temps, secteurs, fuel, cuts).

## Fonctionnement

Un thread `LogMonitorService` (`app/log_monitor.py`) lit en continu les
nouvelles lignes du `server.log` du serveur ACC, les parse (`app/parser.py`)
et les enregistre dans une base SQLite via SQLAlchemy (`app/models.py`) :

- `weekends` : un week-end de serveur (créé au démarrage et à chaque
  `Resetting race weekend`)
- `races` : une ligne par changement de session, liée au week-end en cours
- `drivers` : pilotes vus via `New connection request` / `Creating new car
  connection` / `Recognized reconnect`
- `laps_live` : chaque tour (`carId ... lapTime ...`) **et chaque passage de
  secteur** (ligne avec le lapTime sentinel `35791:23:647` → `lap_time` NULL,
  secteurs S1/S2/S3 conservés), avec fuel, `hasCut` et `SessionOver`
- `servers` : serveurs déclarés (nom, chemin, ports TCP/UDP)

## Installation

```bash
pip install -r requirements.txt        # + requirements-dev.txt pour les tests
```

## Configuration

**Fichier local recommandé** : copier `config.local.example.py` en `config.local.py`
(ignoré par git) et y mettre tes chemins — il a priorité sur les variables
d'environnement :

```python
ACC_LOG_PATH = r"..\accweb_v1.27.0\config\1786545622\log\server.log"
ENTRYLIST_PATH = r"..\accweb_v1.27.0\config\1786545622\cfg\entrylist.json"
```

Sinon, par variables d'environnement (voir `config.py`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `ACC_LOG_PATH` | `server_files/log/server.log` | chemin du `server.log` surveillé (relatif = depuis la racine du dépôt, ex `..\accweb_v1.27.0\config\1786545622\log\server.log`) |
| `ENTRYLIST_PATH` | `server_files/cfg/entrylist.json` | entrylist du serveur (mapping n° de course ↔ SteamID), idem pour les chemins relatifs |
| `DATABASE_URL` | `sqlite:///instance/laps.db` | URI de la base SQLite |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | bind du serveur web |

## Gestion des logs

- `ACC_LOG_PATH` pointe vers le fichier `server.log` **courant** ; le moniteur lit
  uniquement les nouveaux octets (offset persisté par fichier dans
  `instance/monitor_state.json`, donc pas de relecture au redémarrage).
- `ACC_LOGS_DIR` (défaut : le dossier `logs` à côté de `log`) contient les logs
  archivés `logs_*.log` : ils sont rejoués au démarrage et surveillés en continu
  (un nouveau fichier archivé est traité dès qu'il apparaît).
- Si `server.log` est tronqué/recréé plus petit (restart du serveur), l'offset
  repart de 0 automatiquement.
- Une ligne écrite sans retour à la ligne final est attendue avant d'être parsée.

## Lancement

```bash
python run.py
```

Puis ouvrir http://127.0.0.1:5000 — pages : Courses (historique filtrable),
Live (`/api/live_data` rafraîchi en JSON), Pilotes, Serveurs.

## Tests

```bash
python -m pytest tests/ -q
```

## Structure

```
app/
  __init__.py      # factory Flask + routes
  extensions.py    # instance SQLAlchemy
  models.py        # Server, Drivers, Races, WeekEnds, LapLive
  parser.py        # regex et conversions du server.log
  log_monitor.py   # thread de surveillance du log
  db_query.py      # requêtes utilitaires en CLI
  templates/       # pages HTML
config.py
run.py
tests/
```
