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
    subtitles_before, current_subtitle, subtitles_after = surrounding_subtitles(
            matched_episode.subtitles, time)
    if current_subtitle is not None:
        title = '%s - %s - "%s"' % (matched_season.name, matched_episode.name,
                                    re.sub(r'</?[^>]+>', '', current_subtitle.content))
    else:
        title = '%s - %s' % (matched_season.name, matched_episode.name)
    # Prepare response
    return flask.render_template('moment.html',
                                 season=matched_season,
                                 episode=matched_episode,
                                 title=title,
                                 timecode=time,
                                 time_steps=render_time_steps(matched_episode, time),
                                 subtitles_before=subtitles_before,
                                 current_subtitle=current_subtitle,
                                 subtitles_after=subtitles_after)

def strptimecode(td):
    hours = td.total_seconds() // 60 // 60
    minutes = td.total_seconds() // 60 % 60
    seconds = td.total_seconds() % 60
    if hours > 0:
        return '%d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%d:%02d' % (minutes, seconds)

def surrounding_subtitles(subtitles, time):
    RANGE = timedelta(seconds=5)

    # TODO: could do this faster than O(n) with a tree-based lookup or whatever
    surrounding = [s for s in subtitles
                   if s.start >= time - RANGE and s.end <= time + RANGE]
    intersecting = [s for s in surrounding
                    if s.start <= time and s.end >= time]

    if len(intersecting) > 0:
        current = intersecting[0]
    else:
        current = None
    if current is None:
        before = [s for s in surrounding if s.start < time]
    else:
        # s != current broken in srt
        before = [s for s in surrounding if s.start < time and s.start != current.start]
    after = [s for s in surrounding if s.start > time]

    return before, current, after

def render_time_steps(episode, current_time):
    TIME_STEPS = [timedelta(seconds=0.1),
                  timedelta(seconds=0.2),
                  timedelta(seconds=0.5),
                  timedelta(seconds=1)]

    def time_class(td):
        diff = (td - current_time).total_seconds()
        if diff == 0:
            return 'now'
        elif diff < 0:
            return '%.1fs before' % abs(diff)
        else:
            return '%.1fs after' % diff

    times = [Timecode.from_timedelta(current_time - td) for td in TIME_STEPS]
    times += [current_time]
    times += [Timecode.from_timedelta(current_time + td) for td in TIME_STEPS]
    times = filter(lambda t: t >= Timecode(0) and t <= episode.duration, times)
    return [{ 'time': t, 'class': time_class(t) } for t in times]

