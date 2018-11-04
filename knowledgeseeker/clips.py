import flask
import io
import textwrap as tw
from base64 import b64decode
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from knowledgeseeker.database import get_db
from knowledgeseeker.utils import set_expires


bp = flask.Blueprint('clips', __name__)


TEXT_VMARGIN = 0.1
TEXT_SPACING = 4

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


def drawtext(image, top_text, bottom_text):
    MAX_WIDTH = flask.current_app.config.get('SUBTITLES_FONT_MAXWIDTH')
    MAX_LENGTH = MAX_WIDTH*2

    font_path = flask.current_app.config.get('SUBTITLES_FONT', None)
    font = (ImageFont.truetype(
            font=font_path,
            size=flask.current_app.config.get('SUBTITLES_FONT_SIZE'))
        if font_path is not None else None)
    draw = ImageDraw.Draw(image)
    def wrap(t):
        return '\n'.join(tw.wrap(t, width=MAX_WIDTH))

    if top_text != '':
        text = wrap(top_text[:MAX_LENGTH])
        size = draw.multiline_textsize(text, font=font, spacing=TEXT_SPACING)
        pos = (round(image.width/2 - size[0]/2), round(TEXT_VMARGIN*image.height))
        draw.multiline_text(pos, text, font=font,
                            spacing=TEXT_SPACING, align='center')

    if bottom_text != '':
        text = wrap(bottom_text[:MAX_LENGTH])
        size = draw.multiline_textsize(text, font=font, spacing=TEXT_SPACING)
        pos = (round(image.width/2 - size[0]/2),
               image.height - round(TEXT_VMARGIN*image.height) - size[1])
        draw.multiline_text(pos, text, font=font,
                            spacing=TEXT_SPACING, align='center')


def call_with_fonts(callee, *args, **kwargs):
    app_config = flask.current_app.config
    if 'SUBTITLES_FONT' in app_config:
        if 'SUBTITLES_FONTSDIR' in app_config:
            kwargs['fonts_path'] = Path(app_config['SUBTITLES_FONTSDIR'])
            kwargs['font'] = app_config['SUBTITLES_FONT']
        else:
            kwargs['font'] = app_config['SUBTITLES_FONT']
    return callee(*args, **kwargs)
