import flask
from flask_caching import Cache
from os import environ, makedirs
from pathlib import Path

animation_cache = Cache(config={ 'CACHE_TYPE': 'filesystem',
                                 'CACHE_DEFAULT_TIMEOUT': 0,
                                 'CACHE_THRESHOLD': 400 }) # 400*5 MB = 2 GB

def create_app(test_config=None):
    app = flask.Flask(__name__, instance_relative_config=True)
    app.config.from_object('config')
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

    from . import scache
    scache.init_app(app)

    from . import searcher
    app.register_blueprint(searcher.bp)
    searcher.init_app(app)

    init_app(app)

    return app

def init_app(app):
    animation_cache_path = Path(app.instance_path)/'animation_cache'
    animation_cache.init_app(app, config={ 'CACHE_DIR': animation_cache_path })

    @app.route('/')
    def index():
        return flask.render_template('index.html')

    @app.route('/about')
    def about():
        return flask.render_template('about.html')

