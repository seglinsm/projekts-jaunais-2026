from pathlib import Path
import sqlite3

from flask import current_app, g


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = BASE_DIR / "goalbloom.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_db():
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db(database_path=None):
    db_path = Path(database_path or DEFAULT_DATABASE)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.commit()
    connection.close()


def init_app(app):
    app.teardown_appcontext(close_db)
