import flask
import re
from datetime import timedelta

# TODO replace with function decorators
from .clipper import timecode_valid, timecode_in_episode
from .utils import strptimecode, strftimecode, find_episode, http_error, grouper

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
            timecodes = human_strptimecode(s.start)
        else:
            timecodes = '%s - %s' % (human_strptimecode(s.start), human_strptimecode(s.end))
        rendered_subtitles.append({ 'timecode': strptimecode((s.start + s.end)/2),
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
    time = strftimecode(timecode)
    if not timecode_in_episode(time, matched_episode):
        return http_error(416, 'timecode out of range')
    # Locate relevant subtitles
    previous_line, this_line, next_line = surrounding_subtitles(matched_episode.subtitles,
                                                                time)
    if this_line is not None:
        title = '%s - %s - "%s"' % (matched_season.name, matched_episode.name,
                                    re.sub(r'</?[^>]+>', '', this_line))
    else:
        title = '%s - %s' % (season.name, episode.name)
    make_str = lambda line: '' if line is None else line
    return flask.render_template('moment.html',
                                 season=matched_season,
                                 episode=matched_episode,
                                 title=title,
                                 previous_line=make_str(previous_line),
                                 this_line=make_str(this_line),
                                 next_line=make_str(next_line))

def human_strptimecode(td):
    hours = td.total_seconds() // 60 // 60
    minutes = td.total_seconds() // 60 % 60
    seconds = td.total_seconds() % 60
    if hours > 0:
        return '%d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%d:%02d' % (minutes, seconds)

def surrounding_subtitles(subtitles, time):
    # TODO: could do this faster than O(2*n) with a tree-based lookup or whatever
    previous_line = this_line = next_line = None
    for first, second, third in grouper([None] + subtitles + [None], 3):
        if second.start <= time and second.end >= time:
            this_line = second.content
            if first is not None:
                previous_line = first.content
            if third is not None:
                next_line = third.content
            break
    if this_line is None and len(subtitles) > 0:
        first_subtitle = matched_episode.subtitles[0]
        last_subtitle = matched_episode.subtitles[-1]
        if first_subtitle.start > time:
            next_line = first_subtitle
        elif last_subtitle.end < time:
            previous_line = last_subtitle
        else:
            for first, second in grouper(matched_episode.subtitles, 2):
                if first.end < time and second.start > time:
                    previous_line = first.content
                    next_line = second.content
                    break
    return previous_line, this_line, next_line

