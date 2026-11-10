from app import create_app

app = create_app(start_monitor=True)

if __name__ == "__main__":
    app.run(
        debug=True,
        port=app.config["PORT"],
        host=app.config["HOST"],
        use_reloader=False,  # évite de lancer deux fois le watcher
    )
