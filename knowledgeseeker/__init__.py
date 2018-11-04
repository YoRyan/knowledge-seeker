import flask
from os import environ, makedirs
from pathlib import Path

from knowledgeseeker.database import close_connection


def create_app(test_config=None):
    app = flask.Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile('config.py')
    app.config['DEV'] = 'FLASK_ENV' in environ and environ['FLASK_ENV'] == 'development'

    try:
        makedirs(app.instance_path)
    except OSError:
        pass

    from . import clipper, explorer
    app.register_blueprint(clipper.bp)
    app.register_blueprint(explorer.bp)

    from . import library
    library.init_app(app)

    from . import searcher
    app.register_blueprint(searcher.bp)

    init_app(app)

    return app

def init_app(app):
    @app.route('/')
    def index():
        return flask.render_template('index.html')

    @app.route('/about')
    def about():
        return flask.render_template('about.html')

    @app.teardown_appcontext
    def close_db(*args, **kwargs):
        return close_connection(*args, **kwargs)

