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
    # Locate relevant subtitles
    RANGE = timedelta(seconds=5)
    subtitles = [s for s in episode.subtitles
                 if s.start >= timecode - RANGE and s.end <= timecode + RANGE]
    matched_subtitles = [s for s in subtitles
                         if s.start <= timecode and s.end >= timecode]
    if len(matched_subtitles) > 0:
        title = '%s - %s - "%s"' % (season.name, episode.name,
                                    re.sub(r'</?[^>]+>', '', matched_subtitles[0].content))
    else:
        title = '%s - %s' % (season.name, episode.name)
    # Create navigation previews
    TIME_STEPS = [timedelta(seconds=0.1),
                  timedelta(seconds=0.2),
                  timedelta(seconds=0.5),
                  timedelta(seconds=1)]
    step_times = ([Timecode.from_timedelta(timecode - td) for td in reversed(TIME_STEPS)] +
                  [timecode] +
                  [Timecode.from_timedelta(timecode + td) for td in TIME_STEPS])
    step_times = filter(lambda t: t >= Timecode(0) and t <= episode.duration,
                        step_times)
    # Prepare response
    return flask.render_template('moment.html',
                                 title=title,
                                 season=season,
                                 episode=episode,
                                 time=timecode,
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

