import flask
import json
import re
import subprocess
from datetime import datetime, timedelta
from os import environ
from pathlib import Path
from time import mktime
from wsgiref.handlers import format_date_time

from . import animation_cache
from .utils import (Timecode, match_season_episode, episode_has_subtitles,
                    parse_timecode, check_timecode_range, set_expires, static_cached)
from .video import (make_snapshot, make_snapshot_with_subtitles, make_tiny_snapshot,
                    make_gif, make_gif_with_subtitles,
                    make_webm, make_webm_with_subtitles)

bp = flask.Blueprint('clipper', __name__)

@bp.route('/<season>/<episode>/<timecode>/pic')
@match_season_episode
@parse_timecode('timecode')
@set_expires
def snapshot(season, episode, timecode):
    data = make_snapshot(episode.video_path, timecode)
    return flask.Response(data, mimetype='image/jpeg')

@bp.route('/<season>/<episode>/<timecode>/pic/sub')
@match_season_episode
@episode_has_subtitles
@parse_timecode('timecode')
@set_expires
def snapshot_with_subtitles(season, episode, timecode):
    data = call_with_fonts(make_snapshot_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, timecode)
    return flask.Response(data, mimetype='image/jpeg')

@bp.route('/<season>/<episode>/<timecode>/pic/tiny')
@static_cached
@match_season_episode
@parse_timecode('timecode')
@set_expires
def snapshot_tiny(season, episode, timecode):
    data = make_tiny_snapshot(episode.video_path, timecode)
    return flask.Response(data, mimetype='image/jpeg')

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif')
@match_season_episode
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_GIF_LENGTH'])
@set_expires
@animation_cache.cached()
def gif(season, episode, start_timecode, end_timecode):
    data = make_gif(episode.video_path, start_timecode, end_timecode,
                    vres=flask.current_app.config['GIF_VRES'])
    return flask.Response(data, mimetype='image/gif')

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif/sub')
@match_season_episode
@episode_has_subtitles
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_GIF_LENGTH'])
@set_expires
@animation_cache.cached()
def gif_with_subtitles(season, episode, start_timecode, end_timecode):
    data = call_with_fonts(make_gif_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, start_timecode, end_timecode,
                           vres=flask.current_app.config['GIF_VRES'])
    return flask.Response(data, mimetype='image/gif')

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/webm')
@match_season_episode
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_WEBM_LENGTH'])
@set_expires
@animation_cache.cached()
def webm(season, episode, start_timecode, end_timecode):
    data = make_webm(episode.video_path, start_timecode, end_timecode,
                     vres=flask.current_app.config['WEBM_VRES'])
    return flask.Response(data, mimetype='video/webm')

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/webm/sub')
@match_season_episode
@episode_has_subtitles
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_WEBM_LENGTH'])
@set_expires
@animation_cache.cached()
def webm_with_subtitles(season, episode, start_timecode, end_timecode):
    data = call_with_fonts(make_webm_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, start_timecode, end_timecode,
                           vres=flask.current_app.config['WEBM_VRES'])
    return flask.Response(data, mimetype='video/webm')

def call_with_fonts(callee, *args, **kwargs):
    app_config = flask.current_app.config
    if 'SUBTITLES_FONT' in app_config:
        if 'SUBTITLES_FONTSDIR' in app_config:
            kwargs['fonts_path'] = Path(app_config['SUBTITLES_FONTSDIR'])
            kwargs['font'] = app_config['SUBTITLES_FONT']
        else:
            kwargs['font'] = app_config['SUBTITLES_FONT']
    return callee(*args, **kwargs)

    date = datetime.now() + td
    response.headers.set('Expires', format_date_time(mktime(date.timetuple())))

