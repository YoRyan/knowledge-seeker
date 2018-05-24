import flask
import re
from datetime import timedelta

from .utils import Timecode, match_season_episode, parse_timecode, http_error

bp = flask.Blueprint('explorer', __name__)

@bp.route('/<season>/<episode>/')
@match_season_episode
def browse_episode(season, episode):
    subtitles = episode.subtitles
    rendered_subtitles = []
    last_subtitle = None
    for s in subtitles:
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
    subtitles, current_line = close_subtitles(episode, timecode)
    return flask.render_template('moment.html',
                                 season=season,
                                 episode=episode,
                                 timecode=timecode,
                                 subtitles=subtitles,
                                 current_line=current_line,
                                 step_times=step_times(episode, timecode))

@bp.route('/<season>/<episode>/<first_timecode>/<second_timecode>/')
@match_season_episode
@parse_timecode('first_timecode')
@parse_timecode('second_timecode')
def browse_dual_moments(season, episode, first_timecode, second_timecode):
    first_subtitles, first_line = close_subtitles(episode, first_timecode)
    second_subtitles, second_line = close_subtitles(episode, second_timecode)
    return flask.render_template('dual_moments.html',
                                 season=season,
                                 episode=episode,
                                 first_timecode=first_timecode, second_timecode=second_timecode,
                                 first_subtitles=first_subtitles, second_subtitles=second_subtitles,
                                 first_line=first_line, second_line=second_line,
                                 first_step_times=step_times(episode, first_timecode),
                                 second_step_times=step_times(episode, second_timecode))

def strptimecode(td):
    hours = td.total_seconds() // 60 // 60
    minutes = td.total_seconds() // 60 % 60
    seconds = td.total_seconds() % 60
    if hours > 0:
        return '%d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%d:%02d' % (minutes, seconds)

def close_subtitles(episode, timecode):
    RANGE = timedelta(seconds=5)
    surrounding = filter(lambda subtitle: (subtitle.start >= timecode - RANGE and
                                           subtitle.end <= timecode + RANGE),
                         episode.subtitles)
    intersecting = [subtitle for subtitle in surrounding
                    if subtitle.start <= timecode and subtitle.end >= timecode]
    if len(intersecting) > 0:
        # Remove any HTML
        current_line = re.sub(r'</?[^>]+>', '', intersecting[0].content).strip()
        return surrounding, current_line
    else:
        return surrounding, None

def step_times(episode, timecode):
    TIME_STEPS = [timedelta(seconds=0.1),
                  timedelta(seconds=0.2),
                  timedelta(seconds=0.5),
                  timedelta(seconds=1)]
    step_times = ([Timecode.from_timedelta(timecode - td) for td in reversed(TIME_STEPS)] +
                  [timecode] +
                  [Timecode.from_timedelta(timecode + td) for td in TIME_STEPS])
    return filter(lambda t: t >= Timecode(0) and t <= episode.duration, step_times)

