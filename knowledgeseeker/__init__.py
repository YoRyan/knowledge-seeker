import os
from flask import Flask
from pathlib import Path

from .library import load_library_file
from .video import run_ffmpeg

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(SECRET_key='dev')

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import clipper
    app.register_blueprint(clipper.bp)

    init_app(app)

    return app

def init_app(app):
    app.library_data = load_library_file(Path(app.config['LIBRARY']))

