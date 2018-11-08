import json
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext
from srt import parse as parse_srt

import knowledgeseeker.database as database
import knowledgeseeker.ffmpeg as ff


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
        else:
            self.icon = None


class Episode(object):
    def __init__(self, slug, video_path, subtitles_path=None, name=None):
        self.slug = slug
        self.name = name
        self.video_path = video_path
        self.subtitles_path = subtitles_path
        if subtitles_path is None:
            self.subtitles = []
        else:
            with open(subtitles_path) as f:
                self.subtitles = list(parse_srt(f.read()))
                self.subtitles.sort(key=lambda s: s.index)


def load_library_file(library_path):
    with open(library_path, 'rt') as f:
        js_data = json.load(f)
    return [read_season_json(season_data, relative_to=library_path.parent)
            for season_data in js_data]


def read_season_json(season_data, relative_to=Path('.')):
    slug = season_data['seasonSlug']
    name = season_data.get('seasonName', None)

    icon = season_data.get('seasonIcon', None)
    if icon is not None:
        icon = relative_to/Path(icon)

    episodes = season_data.get('episodes', [])
    if episodes != []:
        episodes = [read_episode_json(episode_data, relative_to=relative_to)
                    for episode_data in season_data['episodes']]

    return Season(slug, name=name, episodes=episodes, icon_path=icon)


def read_episode_json(episode_data, relative_to=Path('.')):
    slug = episode_data['episodeSlug']
    name = episode_data.get('episodeName', None)
    video_path = relative_to/Path(episode_data['videoFile'])
    subtitles_path = episode_data.get('subtitleFile', None)
    if subtitles_path is not None:
        subtitles_path = relative_to/Path(subtitles_path)
    return Episode(slug, video_path, subtitles_path=subtitles_path, name=name)


def init_app(app):
    app.cli.add_command(read_library_command)


@click.command('read-library')
@with_appcontext
def read_library_command():
    database.remove()
    db = database.get_db()
    with current_app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

    library_data = load_library_file(Path(current_app.config.get('LIBRARY')))
    database.populate(library_data)

