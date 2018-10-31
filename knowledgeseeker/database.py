import sqlite3
from pathlib import Path

from flask import current_app, g


FILENAME = 'data.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        path = Path(current_app.instance_path)/FILENAME
        db = g._database = sqlite3.connect(str(path))
    return db

def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

