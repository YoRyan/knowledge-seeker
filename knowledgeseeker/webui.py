import re
from urllib.parse import unquote

import flask
from base64 import b64encode

from knowledgeseeker.database import get_db, match_episode, match_season
from knowledgeseeker.utils import Timecode, set_expires, strip_html


bp = flask.Blueprint('webui', __name__)

NAV_STEPS = 3
CLOSE_SUBTITLE_SECS = 3
MAX_SEARCH_LENGTH = 80
N_SEARCH_RESULTS = 50


@bp.route('/')
def index():
    cur = get_db().cursor()
    cur.execute('SELECT slug, name FROM season')
    return flask.render_template('index.html', seasons=cur.fetchall())


@bp.route('/about')
def about():
    return flask.render_template('about.html')


@bp.route('/<season>/')
@match_season
def browse_season(season_id):
    cur = get_db().cursor()
    targs = {}

    # Retrieve season information.
    cur.execute('SELECT slug, icon_png, name FROM season WHERE id=:season_id',
                { 'season_id': season_id })
    res = cur.fetchone()
    targs['season'] = res['slug']
    targs['season_name'] = res['name']
    targs['season_has_icon'] = res['icon_png'] is not None

    # Retrieve episodes.
    cur.execute(
        'SELECT slug, name, duration, snapshot_ms FROM episode '
        ' WHERE season_id=:season_id',
        { 'season_id': season_id })
    targs['episodes'] = cur.fetchall()

    def str_ms(ms):
        return Timecode(milliseconds=ms).str_seconds()
    targs['str_ms'] = str_ms
    return flask.render_template('season.html', **targs)


@bp.route('/<season>/icon')
@set_expires
@match_season
def season_icon(season_id):
    cur = get_db().cursor()

    # Retrieve season information.
    cur.execute('SELECT icon_png FROM season WHERE id=:season_id',
                { 'season_id': season_id })
    res = cur.fetchone()
    icon_data = res['icon_png']
    if icon_data is None:
        flask.abort(404, 'no icon available')

    # Return icon.
    response = flask.make_response(icon_data)
    response.headers.set('Content-Type', 'image/png')
    return response


@bp.route('/<season>/<episode>/')
@match_episode
def browse_episode(season_id, episode_id):
    cur = get_db().cursor()
    targs = {}

    # Retrieve season information.
    cur.execute('SELECT slug, icon_png, name FROM season WHERE id=:season_id',
                { 'season_id': season_id })
    res = cur.fetchone()
    targs['season'] = res['slug']
    targs['season_name'] = res['name']
    targs['season_has_icon'] = res['icon_png'] is not None

    # Retrieve episode information.
    cur.execute('SELECT slug, name FROM episode WHERE id=:episode_id',
                { 'episode_id': episode_id })
    res = cur.fetchone()
    targs['episode'] = res['slug']
    targs['episode_name'] = res['name']

    # Retrieve all subtitles.
    cur.execute(
        'SELECT start_ms, end_ms, snapshot_ms, content FROM subtitle '
        ' WHERE episode_id=:episode_id ORDER BY start_ms',
        { 'episode_id': episode_id })
    res = cur.fetchall()
    if len(res) == 0:
        flask.abort(404, 'no subtitles found')
    targs['subtitles'] = res

    def str_ms(ms):
        return Timecode(milliseconds=ms).str_seconds()
    targs['str_ms'] = str_ms
    return flask.render_template('episode.html', **targs)


@bp.route('/<season>/<episode>/<int:ms>/')
@match_episode
def browse_moment(season_id, episode_id, ms):
    cur = get_db().cursor()
    targs = {'ms': ms}

    # Retrieve season information.
    cur.execute('SELECT slug, icon_png, name FROM season WHERE id=:season_id',
                { 'season_id': season_id })
    res = cur.fetchone()
    targs['season'] = res['slug']
    targs['season_name'] = res['name']
    targs['season_has_icon'] = res['icon_png'] is not None

    # Retrieve episode information.
    cur.execute('SELECT slug, name FROM episode WHERE id=:episode_id',
                { 'episode_id': episode_id })
    res = cur.fetchone()
    targs['episode'] = res['slug']
    targs['episode_name'] = res['name']

    # Locate relevant subtitles.
    cur.execute(
        'SELECT content, start_ms, end_ms, snapshot_ms FROM subtitle '
        ' WHERE episode_id=:episode_id '
        '       AND MIN(ABS(start_ms-:ms), ABS(end_ms-:ms))<=:ms_range',
        { 'episode_id': episode_id, 'ms': ms,
          'ms_range': CLOSE_SUBTITLE_SECS*1000 })
    subtitles = cur.fetchall()
    targs['subtitles'] = subtitles
    targs['current_line'] = next(
        map(lambda row: strip_html(row['content']),
            filter(lambda row: ms >= row['start_ms'] and ms <= row['end_ms'],
                   subtitles)),
        '')

    # Locate surrounding images.
    nav_list = [ms]
    cur.execute(
        '  SELECT ms FROM snapshot WHERE episode_id=:episode_id AND ms<:ms '
        'ORDER BY ms DESC LIMIT :steps',
        { 'episode_id': episode_id, 'ms': ms, 'steps': NAV_STEPS })
    nav_list += [row['ms'] for row in cur.fetchall()]
    cur.execute(
        '  SELECT ms FROM snapshot WHERE episode_id=:episode_id AND ms>:ms '
        'ORDER BY ms ASC LIMIT :steps',
        { 'episode_id': episode_id, 'ms': ms, 'steps': NAV_STEPS })
    nav_list += [row['ms'] for row in cur.fetchall()]
    nav_list.sort()
    targs['nav_list'] = nav_list

    def encode_text(content):
        return b64encode(strip_html(content).encode('utf-8'))
    targs['encode_text'] = encode_text
    return flask.render_template('moment.html', **targs)


@bp.route('/search')
def search():
    query = flask.request.args.get('q')
    if query is None:
        query = ''

    query = unquote(query)
    query = re.sub(r'[^a-zA-Z0-9 \']', '', query)
    query = query[0:MAX_SEARCH_LENGTH]
    if query == '':
        return flask.render_template('search.html', query='')

    cur = get_db().cursor()
    cur.execute('PRAGMA full_column_names = ON')
    cur.execute(
        '    SELECT episode.slug, season.slug, search.snapshot_ms, search.content '
        '           FROM season '
        'INNER JOIN episode ON episode.season_id = season.id '
        'INNER JOIN (SELECT episode_id, snapshot_ms, content FROM subtitle_search '
        '             WHERE content MATCH :query LIMIT :n_results) search '
        '           ON search.episode_id = episode.id',
        { 'query': query, 'n_results': N_SEARCH_RESULTS })
    results = cur.fetchall()
    return flask.render_template('search.html', query=query, results=results,
                                 n_results=len(results))

