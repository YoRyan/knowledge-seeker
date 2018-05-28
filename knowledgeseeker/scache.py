from click import echo
from flask import current_app, make_response, url_for
from mimetypes import guess_extension, guess_type
from os import makedirs, remove
from pathlib import Path
from shutil import rmtree

# NOTE: methods are not yet thread-safe
class StaticCache(object):
    def __init__(self, path):
        self.path = path

    def reset(self):
        makedirs(self.path, exist_ok=True)
        for child in self.path.iterdir():
            if child.is_dir():
                rmtree(child)
            else:
                remove(child)

    def serve(self, endpoint, **values):
        item_path = self._item_path(endpoint, **values)
        matched = [child for child in item_path.parent.iterdir()
                   if child.is_file() and child.stem == item_path.name]
        if len(matched) == 0:
            return None

        item_path = matched[0]
        with open(item_path, 'rb') as f:
            data = f.read()
        mimetype = guess_type(item_path.name)[0]

        response = make_response(data)
        response.headers.set('Content-Type', mimetype)
        return response

    def cache(self, endpoint, **values):
        response = current_app.view_functions[endpoint](**values)
        data = response.get_data()
        mimetype = response.headers.get('Content-Type')
        # Encode the MIME type in a file extension, which can be recognized by
        # this program and by a web server
        extension = guess_extension(mimetype)
        item_path = self._item_path(endpoint, **values)
        item_path = item_path.parent/(item_path.name + extension)
        makedirs(item_path.parent, exist_ok=True)
        with open(item_path, 'wb') as f:
            f.write(data)

    def _item_path(self, endpoint, **values):
        sub = url_for(endpoint, _external=False, **values).lstrip('/')
        return self.path/sub

def init_cache(seasons):
    def cache(season, episode, timecode):
        current_app.static_cache.cache('clipper.snapshot_tiny', season=season.slug,
                                       episode=episode.slug, timecode=str(timecode))
    with current_app.test_request_context():
        current_app.static_cache.reset()
        for season in seasons:
            echo(season.name)
            for episode in season.episodes:
                echo(' - %s' % episode.name)
                # Cache episode preview
                cache(season, episode, episode.preview)
                # Cache subtitle previews
                for subtitle in episode.subtitles:
                    cache(season, episode, subtitle.preview)

def init_app(app):
    cache_path = Path(app.config['CACHE'])
    app.static_cache = StaticCache(cache_path)

