import flask
import io
import json
import re
import subprocess
import textwrap as tw
from base64 import b64decode
from datetime import datetime, timedelta
from os import environ
from pathlib import Path
from time import mktime

from PIL import Image, ImageDraw, ImageFont
from wsgiref.handlers import format_date_time

from knowledgeseeker.database import get_db
from .utils import (Timecode, match_season_episode, episode_has_subtitles,
                    parse_timecode, check_timecode_range, set_expires, static_cached)
from .video import (make_snapshot, make_snapshot_with_subtitles, make_tiny_snapshot,
                    make_gif, make_gif_with_subtitles,
                    make_webm, make_webm_with_subtitles)

bp = flask.Blueprint('clipper', __name__)

@bp.route('/<season>/<episode>/<int:ms>/pic')
@set_expires
def snapshot(season, episode, ms):
    # Load PNG from database.
    cur = get_db().cursor()
    cur.execute(
        'SELECT snapshot.png FROM '
        '       season '
        '       INNER JOIN episode  ON episode.season_id = season.id '
        '       INNER JOIN snapshot ON snapshot.episode_id = episode.id '
        ' WHERE snapshot.ms=:ms', { 'ms': ms })
    res = cur.fetchone()
    if res is None:
        flask.abort(404)
    image = Image.open(io.BytesIO(res['png']))

    # Draw text if requested.
    top_text = b64decode(flask.request.args.get('topb64', '')).decode('ascii')
    bottom_text = b64decode(flask.request.args.get('btmb64', '')).decode('ascii')
    if top_text != '' or bottom_text != '':
        drawtext(image, top_text, bottom_text)

    # Return as compressed JPEG.
    res = io.BytesIO()
    image.save(res, 'jpeg', quality=85)
    return flask.Response(res.getvalue(), mimetype='image/jpeg')

@bp.route('/<season>/<episode>/<int:ms>/pic/tiny')
@set_expires
def snapshot_tiny(season, episode, ms):
    cur = get_db().cursor()
    cur.execute(
        'SELECT snapshot_tiny.jpeg FROM '
        '       season '
        '       INNER JOIN episode       ON episode.season_id = season.id '
        '       INNER JOIN snapshot_tiny ON snapshot_tiny.episode_id = episode.id '
        ' WHERE snapshot_tiny.ms=:ms', { 'ms': ms })
    res = cur.fetchone()
    if res is None:
        flask.abort(404)
    return flask.Response(res['jpeg'], mimetype='image/jpeg')

@bp.route('/<season>/<episode>/<start_timecode>/<end_timecode>/gif')
@match_season_episode
@parse_timecode('start_timecode')
@parse_timecode('end_timecode')
@check_timecode_range('start_timecode', 'end_timecode',
                      lambda: flask.current_app.config['MAX_GIF_LENGTH'])
@set_expires
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
def webm_with_subtitles(season, episode, start_timecode, end_timecode):
    data = call_with_fonts(make_webm_with_subtitles,
                           episode.video_path,
                           episode.subtitles_path, start_timecode, end_timecode,
                           vres=flask.current_app.config['WEBM_VRES'])
    return flask.Response(data, mimetype='video/webm')


def drawtext(image, top_text, bottom_text):
    VMARGIN = round(0.1*image.height)
    SPACING = 4

    font_path = flask.current_app.config.get('SUBTITLES_FONT', None)
    font = (ImageFont.truetype(
            font=font_path,
            size=flask.current_app.config.get('SUBTITLES_FONT_SIZE'))
        if font_path is not None else None)
    draw = ImageDraw.Draw(image)
    def wrap(t):
        return '\n'.join(tw.wrap(
            t,
            width=flask.current_app.config.get('SUBTITLES_FONT_MAXWIDTH')))

    if top_text != '':
        text = wrap(top_text)
        size = draw.multiline_textsize(text, font=font, spacing=SPACING)
        pos = (round(image.width/2 - size[0]/2), VMARGIN)
        draw.multiline_text(pos, text, font=font, spacing=SPACING, align='center')

    if bottom_text != '':
        text = wrap(bottom_text)
        size = draw.multiline_textsize(text, font=font, spacing=SPACING)
        pos = (round(image.width/2 - size[0]/2), image.height - VMARGIN - size[1])
        draw.multiline_text(pos, text, font=font, spacing=SPACING, align='center')


def call_with_fonts(callee, *args, **kwargs):
    app_config = flask.current_app.config
    if 'SUBTITLES_FONT' in app_config:
        if 'SUBTITLES_FONTSDIR' in app_config:
            kwargs['fonts_path'] = Path(app_config['SUBTITLES_FONTSDIR'])
            kwargs['font'] = app_config['SUBTITLES_FONT']
        else:
            kwargs['font'] = app_config['SUBTITLES_FONT']
    return callee(*args, **kwargs)

