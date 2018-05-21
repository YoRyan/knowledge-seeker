import json
from pathlib import Path
from srt import parse as parse_srt

from .video import FfprobeRuntimeError, video_duration

class LoadError(Exception):
    pass

class Season(object):
    def __init__(self, slug, name=None, episodes=[]):
        self.slug = slug
        self.name = name
        self.episodes = episodes

class Episode(object):
    def __init__(self, slug, video_path, name=None, subtitles_path=None,
                 subtitles=[]):
        self.slug = slug
        self.name = name
        self.video_path = video_path
        self.subtitles_path = subtitles_path
        self.subtitles = subtitles

        try:
            self.duration = video_duration(video_path)
        except FfprobeRuntimeError:
            raise LoadError('failed to read video file: %s' % video_path)

def load_library_file(library_path):
    with open(str(library_path), 'rt') as f:
        js_data = json.load(f)
        return [read_season_json(season_data, library_path.parent)
                for season_data in js_data]

def read_season_json(season_data, relative_to_path=Path('.')):
    slug = season_data['seasonSlug']

    if 'seasonName' in season_data:
        name = season_data['seasonName']
    else:
        name = None

    if 'episodes' in season_data:
        episodes = [read_episode_json(episode_data, relative_to_path=relative_to_path)
                    for episode_data in season_data['episodes']]
    else:
        episodes = []

    return Season(slug, name=name, episodes=episodes)

def read_episode_json(episode_data, relative_to_path=Path('.')):
    slug = episode_data['episodeSlug']
    video = relative_to_path / Path(episode_data['videoFile'])

    if 'subtitleFile' in episode_data:
        subtitles_path = relative_to_path / Path(episode_data['subtitleFile'])
        with open(subtitles_path) as f:
            contents = f.read()
        subtitles = list(parse_srt(contents))
        subtitles.sort(key=lambda s: s.index)
    else:
        subtitles_path = None
        subtitles = []

    if 'episodeName' in episode_data:
        name = episode_data['episodeName']
    else:
        name = None

    return Episode(slug, video, name=name, subtitles_path=subtitles_path,
                   subtitles=subtitles)

