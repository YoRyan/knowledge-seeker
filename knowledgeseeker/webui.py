import re
from urllib.parse import unquote

import flask
from base64 import b64encode

from knowledgeseeker.database import get_db
from knowledgeseeker.utils import Timecode, set_expires, strip_html


bp = flask.Blueprint('webui', __name__)

NAV_STEPS = 3
CLOSE_SUBTITLE_SECS = 3
MAX_SEARCH_LENGTH = 80
N_SEARCH_RESULTS = 50


@bp.route('/')
def index():
        return flask.render_template('index.html')


@bp.route('/about')
def about():
        return flask.render_template('about.html')


@bp.route('/<season>/')
def browse_season(season):
    # Check that season is valid.
    cur = get_db().cursor()
    cur.execute(
        'SELECT id, icon_png, name FROM season WHERE slug=:season',
        { 'season': season })
    res = cur.fetchone()
    if res is None:
        flask.abort(404, 'season not found')
    season_name = res['name']
    season_has_icon = res['icon_png'] is not None
    season_key = res['id']

    # Locate episodes.
    cur.execute(
        'SELECT slug, name, duration, snapshot_ms FROM episode '
        ' WHERE season_id=:season_key',
        { 'season_key': season_key })
    episodes = cur.fetchall()

    def str_ms(ms):
        return Timecode(milliseconds=ms).str_seconds()
    return flask.render_template(
        'season.html',
        season=season, season_name=season_name, season_has_icon=season_has_icon,
        episodes=episodes,
        str_ms=str_ms)


@bp.route('/<season>/icon')
@set_expires
def season_icon(season):
    cur = get_db().cursor()
    cur.execute(
        'SELECT icon_png FROM season WHERE slug=:season', { 'season': season })
    res = cur.fetchone()
    if res is None or res['icon_png'] is None:
        flask.abort(404, 'no icon available')

    response = flask.make_response(res['icon_png'])
    response.headers.set('Content-Type', 'image/png')
    return response


@bp.route('/<season>/<episode>/')
def browse_episode(season, episode):
    cur = get_db().cursor()

    # Check that season and episode are valid.
    cur.execute('PRAGMA full_column_names = ON')
    cur.execute(
        'SELECT season.name, season.icon_png, episode.name, episode.id FROM '
        '    season '
        '    INNER JOIN episode ON episode.season_id = season.id '
        ' WHERE season.slug=:season_slug AND episode.slug=:episode_slug',
        { 'season_slug': season, 'episode_slug': episode })
    res = cur.fetchone()
    if res is None:
        flask.abort(404, 'episode not found')
    season_name = res['season.name']
    season_has_icon = res['season.icon_png'] is not None
    episode_name = res['episode.name']
    episode_key = res['episode.id']
    cur.execute('PRAGMA full_column_names = OFF')

    # Retrieve all subtitles.
    cur.execute(
        'SELECT start_ms, end_ms, snapshot_ms, content FROM subtitle '
        ' WHERE episode_id=:episode_key ORDER BY start_ms',
        { 'episode_key': episode_key })
    res = cur.fetchall()
    if len(res) == 0:
        flask.abort(404, 'no subtitles found')

    def str_ms(ms):
        return Timecode(milliseconds=ms).str_seconds()
    return flask.render_template(
        'episode.html',
        season=season, season_name=season_name, season_has_icon=season_has_icon,
        episode=episode, episode_name=episode_name,
        subtitles=res,
        str_ms=str_ms)


@bp.route('/<season>/<episode>/<int:ms>/')
def browse_moment(season, episode, ms):
    cur = get_db().cursor()

    # Check that season, episode, and snapshot time are valid.
    cur.execute('PRAGMA full_column_names = ON')
    cur.execute(
        'SELECT season.slug, season.name, season.icon_png, '
        '       episode.slug, episode.name, episode.id, snapshot.ms FROM '
        '    season '
        '    INNER JOIN episode  ON episode.season_id = season.id '
        '    INNER JOIN snapshot ON snapshot.episode_id = episode.id '
        ' WHERE snapshot.ms=:ms '
        '       AND season.slug=:season_slug '
        '       AND episode.slug=:episode_slug',
        { 'ms': ms, 'season_slug': season, 'episode_slug': episode })
    res = cur.fetchone()
    if res is None:
        flask.abort(404)
    season_name = res['season.name']
    season_has_icon = res['season.icon_png'] is not None
    episode_name = res['episode.name']
    episode_key = res['episode.id']
    cur.execute('PRAGMA full_column_names = OFF')

    # Locate relevant subtitles.
    cur.execute(
        'SELECT content, start_ms, end_ms, snapshot_ms FROM subtitle '
        ' WHERE subtitle.episode_id=:episode_key '
        '       AND MIN(ABS(start_ms-:ms), ABS(end_ms-:ms))<=:ms_range',
        { 'episode_key': episode_key, 'ms': ms,
          'ms_range': CLOSE_SUBTITLE_SECS*1000 })
    subtitles = cur.fetchall()
    current_line = next(
        map(lambda row: strip_html(row['content']),
            filter(lambda row: ms >= row['start_ms'] and ms <= row['end_ms'],
                   subtitles)),
        '')

    # Locate surrounding images.
    nav_list = [ms]
    cur.execute(
        'SELECT ms FROM snapshot WHERE ms<:ms '
        'ORDER BY ms DESC LIMIT :steps',
        { 'ms': ms, 'steps': NAV_STEPS })
    nav_list += [row['ms'] for row in cur.fetchall()]
    cur.execute(
        'SELECT ms FROM snapshot WHERE ms>:ms '
        'ORDER BY ms ASC LIMIT :steps',
        { 'ms': ms, 'steps': NAV_STEPS })
    nav_list += [row['ms'] for row in cur.fetchall()]
    nav_list.sort()

    def encode_text(content):
        return b64encode(strip_html(content).encode('ascii'))
    return flask.render_template(
        'moment.html',
        season=season, season_name=season_name, season_has_icon=season_has_icon,
        episode=episode, episode_name=episode_name,
        ms=ms,
        subtitles=subtitles,
        current_line=current_line,
        nav_list=nav_list,
        encode_text=encode_text)


@bp.route('/search')
def search():
    query = flask.request.args.get('q')
    if query is None:
        query = ''

    query = unquote(query)
    query = re.sub(r'[^a-zA-Z0-9 \']', '', query)
    query = query[0:MAX_SEARCH_LENGTH]

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

