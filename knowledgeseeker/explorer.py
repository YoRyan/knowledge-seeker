import flask
import re
from datetime import timedelta

from .utils import (Timecode, match_season, match_season_episode,
                    episode_has_subtitles, parse_timecode)

bp = flask.Blueprint('explorer', __name__)

@bp.route('/<season>/')
@match_season
def browse_season(season):
    render = lambda episode: { 'timecode': episode.duration/2,
                               'duration': strptimecode(episode.duration),
                               'name': episode.name,
                               'slug': episode.slug }
    return flask.render_template('season.html',
                                 season=season,
                                 episodes=[render(episode) for episode in season.episodes])

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
        if s.end - s.start < timedelta(seconds=1):
            timecodes = strptimecode(s.start)
        else:
            timecodes = '%s - %s' % (strptimecode(s.start), strptimecode(s.end))
        rendered_subtitles.append({ 'timecode': Timecode.from_timedelta((s.start + s.end)/2),
                                    'range': timecodes,
                                    'text': s.content,
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
    # surrounding subtitles
    subtitles = surrounding_subtitles(episode, timecode)
    render = lambda subtitle: { 'start': subtitle.start,
                                'end': subtitle.end,
                                'timecode': Timecode.from_timedelta((subtitle.start + subtitle.end)/2),
                                'content': subtitle.content }
    kwargs['subtitles'] = [render(subtitle) for subtitle in subtitles]
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
    kwargs = {}
    kwargs['season'] = season
    kwargs['episode'] = episode
    kwargs['first_timecode'] = first_timecode
    kwargs['second_timecode'] = second_timecode
    # surrounding subtitles
    first_subtitles = surrounding_subtitles(episode, first_timecode)
    second_subtitles = surrounding_subtitles(episode, second_timecode)
    render = lambda subtitle: { 'start': subtitle.start,
                                'end': subtitle.end,
                                'timecode': Timecode.from_timedelta((subtitle.start + subtitle.end)/2),
                                'content': subtitle.content }
    kwargs['first_subtitles'] = [render(subtitle) for subtitle in first_subtitles]
    kwargs['second_subtitles'] = [render(subtitle) for subtitle in second_subtitles]
    # page title
    kwargs['first_line'] = current_line(episode, first_timecode)
    kwargs['second_line'] = current_line(episode, second_timecode)
    # navigation previews
    kwargs['first_step_times'] = step_times(episode, first_timecode)
    kwargs['second_step_times'] = step_times(episode, second_timecode)
    # render template
    return flask.render_template('dual_moments.html', **kwargs)

def strptimecode(td):
    hours = td.total_seconds() // 60 // 60
    minutes = td.total_seconds() // 60 % 60
    seconds = td.total_seconds() % 60
    if hours > 0:
        return '%d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%d:%02d' % (minutes, seconds)

def surrounding_subtitles(episode, timecode):
    RANGE = timedelta(seconds=5)
    surrounding = [subtitle for subtitle in episode.subtitles
                   if (subtitle.start >= timecode - RANGE and
                       subtitle.end <= timecode + RANGE)]
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
    step_times = ([Timecode.from_timedelta(timecode - td) for td in reversed(TIME_STEPS)] +
                  [timecode] +
                  [Timecode.from_timedelta(timecode + td) for td in TIME_STEPS])
    return filter(lambda t: t >= Timecode(0) and t <= episode.duration, step_times)

