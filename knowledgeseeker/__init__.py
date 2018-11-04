from os import environ, makedirs
from pathlib import Path

import flask


def create_app(test_config=None):
    app = flask.Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile('config.py')
    app.config['DEV'] = 'FLASK_ENV' in environ and environ['FLASK_ENV'] == 'development'

    try:
        makedirs(app.instance_path)
    except OSError:
        pass

    import knowledgeseeker.clips as clips
    app.register_blueprint(clips.bp)

    import knowledgeseeker.webui as webui
    app.register_blueprint(webui.bp)

    import knowledgeseeker.library as library
    library.init_app(app)

    import knowledgeseeker.database as database
    database.init_app(app)

    return app

