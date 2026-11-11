"""Lancement en production derrière un reverse proxy (nginx/Caddy + Let's Encrypt).

Usage :
    pip install -r requirements-prod.txt
    python serve_prod.py

Le moniteur de log démarre avec l'appli. HOST/PORT se règlent dans
config.local.py (ex: HOST="0.0.0.0", PORT=5000). Le reverse proxy fait le HTTPS.
"""

from waitress import serve

from app import create_app

app = create_app(start_monitor=True)

if __name__ == "__main__":
    serve(
        app,
        host=app.config["HOST"],
        port=app.config["PORT"],
        threads=8,
    )
