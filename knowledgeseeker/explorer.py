import flask
import re
from datetime import timedelta

from .utils import (Timecode, match_season, match_season_episode,
                    episode_has_subtitles, parse_timecode, set_expires)

bp = flask.Blueprint('explorer', __name__)

@bp.route('/<season>/')
@match_season
def browse_season(season):
    return flask.render_template('season.html', season=season)

@bp.route('/<season>/icon')
@match_season
@set_expires
def season_icon(season):
    if season.icon is None:
        flask.abort(404, 'no icon available')

    response = flask.make_response(season.icon)
    response.headers.set('Content-Type', season.icon_mime)
    return response

@bp.route('/<season>/<episode>/')
@match_season_episode
@episode_has_subtitles
def browse_episode(season, episode):
    rendered_subtitles = []
    last_subtitle = None
    for s in episode.subtitles:
        if last_subtitle is not None:
            time_since_last = (s.start - last_subtitle.start).total_seconds()
        else:
            time_since_last = 0
        rendered_subtitles.append({ 'preview': s.preview,
                                    'start': s.start,
                                    'end': s.end,
                                    'nav': s.nav,
                                    'content': s.content,
                                    'time_since_last': time_since_last })
        last_subtitle = s
    return flask.render_template('episode.html',
                                 season=season,
                                 episode=episode,
                                 subtitles=rendered_subtitles)

@bp.route('/<season>/<episode>/<timecode>/')
@match_season_episode
@parse_timecode('timecode')
def browse_moment(season, episode, timecode):
    kwargs = {}
    kwargs['season'] = season
    kwargs['episode'] = episode
    kwargs['timecode'] = timecode
    # timecodes for split command
    if timecode == episode.duration:
        split_timecodes = [timecode - timedelta(seconds=3), timecode]
    else:
        split_timecodes = [timecode, timecode + timedelta(seconds=3)]
    kwargs['split_timecodes'] = split_timecodes
    # surrounding subtitles
    kwargs['subtitles'] = surrounding_subtitles(episode, timecode)
    # page title
    kwargs['current_line'] = current_line(episode, timecode)
    # navigation previews
    kwargs['step_times'] = step_times(episode, timecode)
    # render template
    return flask.render_template('moment.html', **kwargs)

@bp.route('/<season>/<episode>/<first_timecode>/<second_timecode>/')
@match_season_episode
@parse_timecode('first_timecode')
@parse_timecode('second_timecode')
def browse_dual_moments(season, episode, first_timecode, second_timecode):
    if second_timecode <= first_timecode:
        flask.abort(400, 'bad time range')

    max_duration = max(flask.current_app.config['MAX_GIF_LENGTH'].total_seconds(),
                       flask.current_app.config['MAX_WEBM_LENGTH'].total_seconds())
    max_second_timecode = first_timecode + timedelta(seconds=max_duration)
    if second_timecode > max_second_timecode:
        flask.abort(400, 'time range too large')

    kwargs = {}
    kwargs['season'] = season
    kwargs['episode'] = episode
    kwargs['first_timecode'] = first_timecode
    kwargs['second_timecode'] = second_timecode
    # surrounding subtitles
    kwargs['first_subtitles'] = surrounding_subtitles(episode, first_timecode)
    # page title
    kwargs['first_line'] = current_line(episode, first_timecode)
    kwargs['second_line'] = current_line(episode, second_timecode)
    # navigation previews
    kwargs['first_step_times'] = filter(lambda t: t < second_timecode,
                                        step_times(episode, first_timecode))
    kwargs['second_step_times'] = filter(lambda t: (t > first_timecode and
                                                    t <= max_second_timecode),
                                         step_times(episode, second_timecode))
    kwargs['intermediate_times'] = intermediate_times(first_timecode, second_timecode)
    # gif/webm range limits
    kwargs['max_gif_secs'] = flask.current_app.config['MAX_GIF_LENGTH'].total_seconds()
    kwargs['max_webm_secs'] = flask.current_app.config['MAX_WEBM_LENGTH'].total_seconds()
    # render template
    return flask.render_template('dual_moments.html', **kwargs)

def surrounding_subtitles(episode, timecode):
    N_SURROUNDING = 2

    # Locate the "closest" subtitle
    def distance(subtitle):
        if subtitle.start <= timecode and subtitle.end >= timecode:
            return timedelta(0)
        else:
            return min(abs(subtitle.start - timecode), abs(subtitle.end - timecode))
    closest = sorted(episode.subtitles, key=distance)[0]
    idx = episode.subtitles.index(closest)
    surrounding = (episode.subtitles[idx - N_SURROUNDING:idx] +
                   [closest] +
                   episode.subtitles[idx + 1:idx + N_SURROUNDING + 1])
    return surrounding

def current_line(episode, timecode):
    intersecting = [subtitle for subtitle in episode.subtitles
                    if subtitle.start <= timecode and subtitle.end >= timecode]
    if len(intersecting) > 0:
        return re.sub(r'</?[^>]+>', '', intersecting[0].content).strip()
    else:
        return None

def step_times(episode, timecode):
    TIME_STEPS = [timedelta(seconds=0.1),
                  timedelta(seconds=0.2),
                  timedelta(seconds=0.5),
                  timedelta(seconds=1)]
    step_times = ([timecode - td for td in reversed(TIME_STEPS)] +
                  [timecode] +
                  [timecode + td for td in TIME_STEPS])
    return filter(lambda t: t >= Timecode(0) and t <= episode.duration, step_times)

def intermediate_times(start_timecode, end_timecode):
    secs = (end_timecode - start_timecode).total_seconds()
    if secs % 1 == 0:
        return [start_timecode + timedelta(seconds=int(s))
                for s in range(1, int(secs))]
    else:
        return [start_timecode + timedelta(seconds=int(s))
                for s in range(1, int(secs) + 1)]

