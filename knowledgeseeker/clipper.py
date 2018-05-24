import flask
import json
import re
import subprocess
from datetime import timedelta
from os import environ
from pathlib import Path

from . import cache
from .utils import (Timecode, match_season_episode, episode_has_subtitles,
                    parse_timecode, check_timecode_range, http_error)
from .video import (make_snapshot, make_snapshot_with_subtitles,
                    make_gif, make_gif_with_subtitles,
                    make_webm, make_webm_with_subtitles)

MAX_GIF_SECS = 10
MAX_WEBM_SECS = 20
GIF_VRES = 360

bp = flask.Blueprint('clipper', __name__)

@bp.route('/<season>/<episode>/<timecode>/pic')
@match_season_episode
@parse_timecode('timecode')
def snapshot(season, episode, timecode):
    data = make_snapshot(episode.video_path, timecode)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/jpeg')
    return response

@bp.route('/<season>/<episode>/<timecode>/pic/sub')
@match_season_episode
@episode_has_subtitles
@parse_timecode('timecode')
def snapshot_with_subtitles(season, episode, timecode):
    data = call_with_fonts(make_snapshot_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, timecode)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/jpeg')
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif')
@cache.cached(timeout=None)
@match_season_episode
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      timedelta(seconds=MAX_GIF_SECS))
def gif(season, episode, start_timecode, end_timecode):
    data = make_gif(episode.video_path, start_timecode, end_timecode)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/gif')
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif/sub')
@cache.cached(timeout=None)
@match_season_episode
@episode_has_subtitles
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      timedelta(seconds=MAX_GIF_SECS))
def gif_with_subtitles(season, episode, start_timecode, end_timecode):
    data = call_with_fonts(make_gif_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, start_timecode, end_timecode)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/gif')
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/webm')
@cache.cached(timeout=None)
@match_season_episode
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      timedelta(seconds=MAX_WEBM_SECS))
def webm(season, episode, start_timecode, end_timecode):
    data = make_webm(episode.video_path, start_timecode, end_timecode)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'video/webm')
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/webm/sub')
@cache.cached(timeout=None)
@match_season_episode
@episode_has_subtitles
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      timedelta(seconds=MAX_WEBM_SECS))
def webm_with_subtitles(season, episode, start_timecode, end_timecode):
    data = call_with_fonts(make_webm_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, start_timecode, end_timecode)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'video/webm')
    return response

@bp.route('/<season>/<episode>/subtitles')
@match_season_episode
@episode_has_subtitles
def subtitles(season, episode):
    subtitle_to_js = lambda s: { 'start': s.start, 'end': s.end, 'text': s.content }
    data = json.dumps([subtitle_to_js(s) for s in episode.subtitles])
    response = flask.make_response(data)
    response.headers.set('Content-type', 'application/json')
    return response

def call_with_fonts(callee, *args, **kwargs):
    app_config = flask.current_app.config
    if 'SUBTITLES_FONT' in app_config:
        if 'SUBTITLES_FONTSDIR' in app_config:
            kwargs['fonts_path'] = Path(app_config['SUBTITLES_FONTSDIR'])
            kwargs['font'] = app_config['SUBTITLES_FONT']
        else:
            kwargs['font'] = app_config['SUBTITLES_FONT']
    return callee(*args, **kwargs)

