import flask

from .utils import find_episode, http_error

bp = flask.Blueprint('explorer', __name__)

@bp.route('/<season>/<episode>')
def browse_episode(season, episode):
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is not None:
        title = '%s - %s' % (matched_season.name, matched_episode.name)
        return flask.render_template('episode.html', title=title)
    else:
        return http_error(404, 'season/episode not found')

