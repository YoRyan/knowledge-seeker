import flask
import json
import re
import subprocess
from datetime import datetime, timedelta
from os import environ
from pathlib import Path
from time import mktime
from wsgiref.handlers import format_date_time

from . import cache
from .utils import (Timecode, match_season_episode, episode_has_subtitles,
                    parse_timecode, check_timecode_range, http_error)
from .video import (make_snapshot, make_snapshot_with_subtitles, make_tiny_snapshot,
                    make_gif, make_gif_with_subtitles,
                    make_webm, make_webm_with_subtitles)

bp = flask.Blueprint('clipper', __name__)

@bp.route('/<season>/<episode>/<timecode>/pic')
@match_season_episode
@parse_timecode('timecode')
def snapshot(season, episode, timecode):
    data = make_snapshot(episode.video_path, timecode)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/jpeg')
    set_expires_header(response, flask.current_app.config['HTTP_CACHE_EXPIRES'])
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
    set_expires_header(response, flask.current_app.config['HTTP_CACHE_EXPIRES'])
    return response

@bp.route('/<season>/<episode>/<timecode>/pic/tiny')
@match_season_episode
@parse_timecode('timecode')
def snapshot_tiny(season, episode, timecode):
    data = make_tiny_snapshot(episode.video_path, timecode)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/jpeg')
    set_expires_header(response, flask.current_app.config['HTTP_CACHE_EXPIRES'])
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif')
@cache.cached(timeout=None)
@match_season_episode
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_GIF_LENGTH'])
def gif(season, episode, start_timecode, end_timecode):
    data = make_gif(episode.video_path, start_timecode, end_timecode,
                    vres=flask.current_app.config['GIF_VRES'])
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/gif')
    set_expires_header(response, flask.current_app.config['HTTP_CACHE_EXPIRES'])
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif/sub')
@cache.cached(timeout=None)
@match_season_episode
@episode_has_subtitles
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_GIF_LENGTH'])
def gif_with_subtitles(season, episode, start_timecode, end_timecode):
    data = call_with_fonts(make_gif_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, start_timecode, end_timecode,
                           vres=flask.current_app.config['GIF_VRES'])
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/gif')
    set_expires_header(response, flask.current_app.config['HTTP_CACHE_EXPIRES'])
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/webm')
@cache.cached(timeout=None)
@match_season_episode
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_WEBM_LENGTH'])
def webm(season, episode, start_timecode, end_timecode):
    data = make_webm(episode.video_path, start_timecode, end_timecode,
                     vres=flask.current_app.config['WEBM_VRES'])
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'video/webm')
    set_expires_header(response, flask.current_app.config['HTTP_CACHE_EXPIRES'])
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/webm/sub')
@cache.cached(timeout=None)
@match_season_episode
@episode_has_subtitles
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_WEBM_LENGTH'])
def webm_with_subtitles(season, episode, start_timecode, end_timecode):
    data = call_with_fonts(make_webm_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, start_timecode, end_timecode,
                           vres=flask.current_app.config['WEBM_VRES'])
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'video/webm')
    set_expires_header(response, flask.current_app.config['HTTP_CACHE_EXPIRES'])
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

def set_expires_header(response, td):
    date = datetime.now() + td
    response.headers.set('Expires', format_date_time(mktime(date.timetuple())))

