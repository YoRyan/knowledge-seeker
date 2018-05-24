import flask
import re
from datetime import timedelta

# TODO replace with function decorators
from .clipper import timecode_valid, timecode_in_episode
from .utils import Timecode, find_episode, http_error

bp = flask.Blueprint('explorer', __name__)

@bp.route('/<season>/<episode>/')
def browse_episode(season, episode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    # Process subtitles for rendering
    subtitles = matched_episode.subtitles
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
                                 season=matched_season,
                                 episode=matched_episode,
                                 subtitles=rendered_subtitles)

@bp.route('/<season>/<episode>/<timecode>/')
def browse_moment(season, episode, timecode):
    # Find episode
    matched_season, matched_episode = find_episode(season, episode)
    if matched_episode is None:
        return http_error(404, 'season/episode not found')
    # Check timecodes
    if not timecode_valid(timecode):
        return http_error(400, 'invalid timecode format')
    time = Timecode.strftimecode(timecode)
    if not timecode_in_episode(time, matched_episode):
        return http_error(416, 'timecode out of range')
    # Locate relevant subtitles
    RANGE = timedelta(seconds=5)
    subtitles = [s for s in matched_episode.subtitles
                 if s.start >= time - RANGE and s.end <= time + RANGE]
    matched_subtitles = [s for s in subtitles
                         if s.start <= time and s.end >= time]
    if len(matched_subtitles) > 0:
        title = '%s - %s - "%s"' % (matched_season.name, matched_episode.name,
                                    re.sub(r'</?[^>]+>', '', matched_subtitles[0].content))
    else:
        title = '%s - %s' % (matched_season.name, matched_episode.name)
    # Create navigation previews
    TIME_STEPS = [timedelta(seconds=0.1),
                  timedelta(seconds=0.2),
                  timedelta(seconds=0.5),
                  timedelta(seconds=1)]
    step_times = ([Timecode.from_timedelta(time - td) for td in reversed(TIME_STEPS)] +
                  [time] +
                  [Timecode.from_timedelta(time + td) for td in TIME_STEPS])
    step_times = filter(lambda t: t >= Timecode(0) and t <= matched_episode.duration,
                        step_times)
    # Prepare response
    return flask.render_template('moment.html',
                                 title=title,
                                 season=matched_season,
                                 episode=matched_episode,
                                 time=time,
                                 subtitles=subtitles,
                                 step_times=step_times)

def strptimecode(td):
    hours = td.total_seconds() // 60 // 60
    minutes = td.total_seconds() // 60 % 60
    seconds = td.total_seconds() % 60
    if hours > 0:
        return '%d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%d:%02d' % (minutes, seconds)

