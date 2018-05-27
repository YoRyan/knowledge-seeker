import click
import json
import os
import pickle
from flask import current_app
from flask.cli import with_appcontext
from mimetypes import guess_type
from pathlib import Path
from shutil import rmtree
from srt import parse as parse_srt

from .utils import Timecode
from .video import FfprobeRuntimeError, make_tiny_snapshot, video_duration

PREVIEW_CACHE_DIR = 'preview_cache'
LIBRARY_PICKLE_FILE = 'library_data.P'

class LoadError(Exception):
    pass

class Season(object):
    def __init__(self, slug, name=None, episodes=[], icon_path=None):
        self.slug = slug
        self.name = name
        self.episodes = episodes
        if icon_path is not None:
            with open(icon_path, 'rb') as f:
                self.icon = f.read()
            self.icon_mime = guess_type(str(icon_path))[0]
        else:
            self.icon = None

class Episode(object):
    def __init__(self, slug, video_path, name=None, subtitles_path=None,
                 subtitles=[]):
        self.slug = slug
        self.name = name
        self.video_path = video_path
        self.subtitles_path = subtitles_path
        self.subtitles = [Subtitle(Timecode.from_timedelta(subtitle.start),
                                   Timecode.from_timedelta(subtitle.end),
                                   subtitle.content, self)
                          for subtitle in subtitles]
        # video duration
        try:
            self.duration = video_duration(video_path)
        except FfprobeRuntimeError:
            raise LoadError('failed to read video file: %s' % video_path)
        # preview thumbnail
        self.preview = self.duration/2

class Subtitle(object):
    def __init__(self, start, end, content, episode):
        self.start = start
        self.end = end
        self.content = content
        # preview thumbnail
        self.preview = (start + end)/2
        # 10% buffer to deal with slightly overlapping subtitles
        self.nav = start + (end - start)*0.1

class PreviewCache(object):
    def __init__(self, path):
        self.path = path
    def reset(self):
        if self.path.is_dir():
            rmtree(self.path)
        PreviewCache._mkdir(self.path)
    def serve(self, season, episode, timecode):
        path = self.path / season.slug / episode.slug / (str(timecode) + '.jpg')
        if path.is_file():
            with open(path, 'rb') as f:
                return f.read()
        else:
            return None
    def cache(self, season, episode, timecode):
        PreviewCache._mkdir(self.path)
        PreviewCache._mkdir(self.path / season.slug)
        PreviewCache._mkdir(self.path / season.slug / episode.slug)

        path = self.path / season.slug / episode.slug / (str(timecode) + '.jpg')
        data = make_tiny_snapshot(episode.video_path, timecode)
        with open(path, 'wb') as f:
            f.write(data)
    def _mkdir(path):
        try:
            os.makedirs(path)
        except OSError:
            pass

def load_library_file(library_path):
    with open(str(library_path), 'rt') as f:
        js_data = json.load(f)
        return [read_season_json(season_data, library_path.parent)
                for season_data in js_data]

def read_season_json(season_data, relative_to_path=Path('.')):
    slug = season_data['seasonSlug']
    name = season_data.get('seasonName', None)

    icon = season_data.get('seasonIcon', None)
    if icon is not None:
        icon = relative_to_path / Path(icon)

    episodes = season_data.get('episodes', [])
    if episodes != []:
        episodes = [read_episode_json(episode_data, relative_to_path=relative_to_path)
                    for episode_data in season_data['episodes']]

    return Season(slug, name=name, episodes=episodes, icon_path=icon)

def read_episode_json(episode_data, relative_to_path=Path('.')):
    slug = episode_data['episodeSlug']
    video = relative_to_path / Path(episode_data['videoFile'])
    name = episode_data.get('episodeName', None)

    subtitles_path = episode_data.get('subtitleFile', None)
    if subtitles_path is not None:
        subtitles_path = relative_to_path / Path(subtitles_path)
        with open(subtitles_path) as f:
            contents = f.read()
        subtitles = list(parse_srt(contents))
        subtitles.sort(key=lambda s: s.index)
    else:
        subtitles = []

    return Episode(slug, video, name=name, subtitles_path=subtitles_path,
                   subtitles=subtitles)

def load_pickle_file(path):
    with open(path, 'rb') as f:
        return pickle.load(f)

def save_pickle_file(library_data, path):
    with open(path, 'wb') as f:
        pickle.dump(library_data, f)

@click.command('read-library')
@with_appcontext
def read_library_command():
    instance_path = Path(current_app.instance_path)
    # probe library metadata
    library_data = load_library_file(Path(current_app.config['LIBRARY']))
    save_pickle_file(library_data, instance_path / LIBRARY_PICKLE_FILE)
    # recreate the preview cache (takes a long time)
    current_app.preview_cache.reset()
    for season in library_data:
        click.echo(season.name)
        for episode in season.episodes:
            click.echo(' - %s' % episode.name)
            current_app.preview_cache.cache(season, episode, episode.preview)
            for subtitle in episode.subtitles:
                current_app.preview_cache.cache(season, episode, subtitle.preview)

def init_app(app):
    instance_path = Path(app.instance_path)
    # load library metadata
    try:
        app.library_data = load_pickle_file(instance_path / LIBRARY_PICKLE_FILE)
    except FileNotFoundError:
        app.library_data = []
    app.cli.add_command(read_library_command)
    # tiny snapshot cache
    app.preview_cache = PreviewCache(instance_path / PREVIEW_CACHE_DIR)

