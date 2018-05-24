import flask
import json
import re
import subprocess
from datetime import timedelta
from os import environ
from pathlib import Path

from . import cache
from .utils import Timecode, find_episode, http_error
from .video import (make_snapshot, make_snapshot_with_subtitles,
                    make_gif, make_gif_with_subtitles,
                    make_webm, make_webm_with_subtitles)

MAX_GIF_SECS = 10
MAX_WEBM_SECS = 20
GIF_VRES = 360

bp = flask.Blueprint('clipper', __name__)

@bp.route('/<season>/<episode>/<timecode>/pic')
def snapshot(season, episode, timecode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    # Check timecodes
    if not timecode_valid(timecode):
        return http_error(400, 'invalid timecode format')
    time = Timecode.strftimecode(timecode)
    if not timecode_in_episode(time, matched_episode):
        return http_error(416, 'timecode out of range')
    # Prepare response
    data = make_snapshot(matched_episode.video_path, time)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/jpeg')
    return response

@bp.route('/<season>/<episode>/<timecode>/pic/sub')
def snapshot_with_subtitles(season, episode, timecode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    elif matched_episode.subtitles_path is None:
        return http_error(404, 'no subtitles available')
    # Check timecodes
    if not timecode_valid(timecode):
        return http_error(400, 'invalid timecode format')
    time = Timecode.strftimecode(timecode)
    if not timecode_in_episode(time, matched_episode):
        return http_error(416, 'timecode out of range')
    # Prepare response
    data = call_with_fonts(make_snapshot_with_subtitles,
                           matched_episode.video_path,
                           matched_episode.subtitles_path, time)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/jpeg')
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif')
@cache.cached(timeout=None)
def gif(season, episode, start_timecode, end_timecode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    # Check timecodes
    if not timecode_valid(start_timecode) or not timecode_valid(end_timecode):
        return http_error(400, 'invalid timecode format')
    start = Timecode.strftimecode(start_timecode)
    end = Timecode.strftimecode(end_timecode)
    if not timecode_in_episode(start, matched_episode):
        return http_error(416, 'start time out of range')
    elif not timecode_in_episode(end, matched_episode):
        # Fail gracefully; set the end marker to the end of the episode
        end = matched_episode.duration
    if start >= end:
        return http_error(400, 'bad time range')
    elif end - start > timedelta(seconds=MAX_GIF_SECS):
        return http_error(416, 'requested time range exceeds maximum limit')
    # Prepare response
    data = make_gif(matched_episode.video_path, start, end)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/gif')
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif/sub')
@cache.cached(timeout=None)
def gif_with_subtitles(season, episode, start_timecode, end_timecode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    elif matched_episode.subtitles_path is None:
        return http_error(404, 'no subtitles available')
    # Check timecodes
    if not timecode_valid(start_timecode) or not timecode_valid(end_timecode):
        return http_error(400, 'invalid timecode format')
    start = Timecode.strftimecode(start_timecode)
    end = Timecode.strftimecode(end_timecode)
    if not timecode_in_episode(start, matched_episode):
        return http_error(416, 'start time out of range')
    elif not timecode_in_episode(end, matched_episode):
        # Fail gracefully; set the end marker to the end of the episode
        end = matched_episode.duration
    if start >= end:
        return http_error(400, 'bad time range')
    elif end - start > timedelta(seconds=MAX_GIF_SECS):
        return http_error(416, 'requested time range exceeds maximum limit')
    # Prepare response
    data = call_with_fonts(make_gif_with_subtitles,
                           matched_episode.video_path,
                           matched_episode.subtitles_path, start, end)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'image/gif')
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/webm')
@cache.cached(timeout=None)
def webm(season, episode, start_timecode, end_timecode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    # Check timecodes
    if not timecode_valid(start_timecode) or not timecode_valid(end_timecode):
        return http_error(400, 'invalid timecode format')
    start = Timecode.strftimecode(start_timecode)
    end = Timecode.strftimecode(end_timecode)
    if not timecode_in_episode(start, matched_episode):
        return http_error(416, 'start time out of range')
    elif not timecode_in_episode(end, matched_episode):
        # Fail gracefully; set the end marker to the end of the episode
        end = matched_episode.duration
    if start >= end:
        return http_error(400, 'bad time range')
    elif end - start > timedelta(seconds=MAX_WEBM_SECS):
        return http_error(416, 'requested time range exceeds maximum limit')
    # Prepare response
    data = make_webm(matched_episode.video_path, start, end)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'video/webm')
    return response

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/webm/sub')
@cache.cached(timeout=None)
def webm_with_subtitles(season, episode, start_timecode, end_timecode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    # Check timecodes
    if not timecode_valid(start_timecode) or not timecode_valid(end_timecode):
        return http_error(400, 'invalid timecode format')
    start = Timecode.strftimecode(start_timecode)
    end = Timecode.strftimecode(end_timecode)
    if not timecode_in_episode(start, matched_episode):
        return http_error(416, 'start time out of range')
    elif not timecode_in_episode(end, matched_episode):
        # Fail gracefully; set the end marker to the end of the episode
        end = matched_episode.duration
    if start >= end:
        return http_error(400, 'bad time range')
    elif end - start > timedelta(seconds=MAX_WEBM_SECS):
        return http_error(416, 'requested time range exceeds maximum limit')
    # Prepare response
    data = call_with_fonts(make_webm_with_subtitles,
                           matched_episode.video_path,
                           matched_episode.subtitles_path, start, end)
    response = flask.make_response(data)
    response.headers.set('Content-Type', 'video/webm')
    return response

@bp.route('/<season>/<episode>/subtitles')
def subtitles(season, episode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    elif matched_episode.subtitles_path is None:
        return http_error(404, 'no subtitles available')
    # Return json object
    subtitle_to_js = lambda s: { 'start': s.start, 'end': s.end, 'text': s.content }
    data = json.dumps([subtitle_to_js(s) for s in matched_episode.subtitles])
    response = flask.make_response(data)
    response.headers.set('Content-type', 'application/json')
    return response

def timecode_valid(timecode):
    return re.match(r'^(\d?\d:)?[0-5]?\d:[0-5]?\d(\.\d\d?\d?)?$', timecode)

def timecode_in_episode(timecode, episode):
    return timecode >= Timecode(0) and timecode <= episode.duration

def call_with_fonts(callee, *args, **kwargs):
    app_config = flask.current_app.config
    if 'SUBTITLES_FONT' in app_config:
        if 'SUBTITLES_FONTSDIR' in app_config:
            kwargs['fonts_path'] = Path(app_config['SUBTITLES_FONTSDIR'])
            kwargs['font'] = app_config['SUBTITLES_FONT']
        else:
            kwargs['font'] = app_config['SUBTITLES_FONT']
    return callee(*args, **kwargs)

