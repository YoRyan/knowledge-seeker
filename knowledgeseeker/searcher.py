import re
from urllib.parse import unquote

import flask

from knowledgeseeker.database import get_db


MAX_LENGTH = 80
N_RESULTS = 50

bp = flask.Blueprint('searcher', __name__)


@bp.route('/search')
def do_search():
    query = flask.request.args.get('q')
    if query is None:
        query = ''

    query = unquote(query)
    query = re.sub(r'[^a-zA-Z0-9 \']', '', query)
    query = query[0:MAX_LENGTH]

    cur = get_db().cursor()
    cur.execute('PRAGMA full_column_names = ON')
    cur.execute(
        '    SELECT episode.slug, season.slug, search.snapshot_ms, search.content '
        '           FROM season '
        'INNER JOIN episode ON episode.season_id = season.id '
        'INNER JOIN (SELECT episode_id, snapshot_ms, content FROM subtitle_search '
        '             WHERE content MATCH :query LIMIT :results) search '
        '           ON search.episode_id = episode.id',
        { 'query': query, 'results': N_RESULTS })
    results = cur.fetchall()
    return flask.render_template('search.html', query=query, results=results,
                                 n_results=len(results))

