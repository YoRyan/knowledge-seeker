import flask
import re
import whoosh
import whoosh.index
from pathlib import Path
from shutil import rmtree
from urllib.parse import unquote
from whoosh.fields import Schema, ID, TEXT, STORED
from whoosh.qparser import QueryParser

INDEX_DIR = 'subtitle_index'
QUERY_STRING_ENCODING = 'ascii'
QUERY_STRING_MAX_LENGTH = 80
N_RESULTS = 30

bp = flask.Blueprint('searcher', __name__)

@bp.route('/search')
def do_search():
    index = flask.current_app.subtitle_index
    if index is None:
        flask.abort(501, 'search not available')

    search_query = flask.request.args.get('q')
    if search_query is None:
        return flask.redirect(flask.url_for('explorer.browse_index'))

    search_query = unquote(search_query)
    search_query = re.sub(r'[^a-zA-Z0-9 ]', '', search_query)
    search_query = search_query[0:QUERY_STRING_MAX_LENGTH]

    with index.searcher() as searcher:
        query = QueryParser('content', index.schema).parse(search_query)
        results = searcher.search(query, limit=N_RESULTS)
        return flask.render_template('search.html',
                                     query=search_query,
                                     n_results=len(results),
                                     results=results)

def init_subtitle_search(seasons):
    # Create schema
    schema = Schema(season=ID, episode=ID, content=TEXT(stored=True),
                    season_slug=STORED, episode_slug=STORED,
                    index=STORED, timecode=STORED)

    # Create the index
    index_path = Path(flask.current_app.instance_path)/INDEX_DIR
    if index_path.is_dir():
        rmtree(index_path)
    index_path.mkdir(exist_ok=True)
    index = whoosh.index.create_in(index_path, schema)

    # Populate the index
    writer = index.writer()
    for season in seasons:
        for episode in season.episodes:
            for i, subtitle in enumerate(episode.subtitles):
                content = re.sub(r'</?[^>]+>', '', subtitle.content)
                writer.add_document(season=season.name,
                                    episode=episode.name,
                                    content=content,
                                    season_slug=season.slug,
                                    episode_slug=episode.slug,
                                    index=i,
                                    timecode=str(subtitle.preview))
    writer.commit()

def init_app(app):
    index_path = Path(app.instance_path)/INDEX_DIR
    try:
        app.subtitle_index = whoosh.index.open_dir(index_path)
    except whoosh.index.EmptyIndexError:
        app.subtitle_index = None

