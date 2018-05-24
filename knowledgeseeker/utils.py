import flask
import re

from datetime import timedelta
from functools import wraps

class Timecode(timedelta):
    def __str__(self):
        av = abs(self)
        milliseconds = round(av.microseconds/1000)
        seconds = av.seconds % 60
        minutes = av.seconds // 60 % 60
        hours = av.seconds // 60 // 60
        if hours > 0:
            string = '%02d:%02d:%02d.%03d' % (hours, minutes, seconds, milliseconds)
        else:
            string = '%02d:%02d.%03d' % (minutes, seconds, milliseconds)
        if self >= timedelta(0):
            return string
        else:
            return '-%s' % string
    def strftimecode(s):
        match = re.search(r'^(\d*:)?(\d+):(\d+\.?\d*)$', s)
        if match is not None:
            groups = match.groups()
            if groups[0] is None:
                hours = 0
            else:
                hours = int(groups[0][:-1])
            minutes = int(groups[1])
            milliseconds = round(float(groups[2])*1000)
            return Timecode(hours=hours, minutes=minutes, milliseconds=milliseconds)
        else:
            raise ValueError('invalid timecode format: \'%s\'' % tc)
    def from_timedelta(td):
        return Timecode(days=td.days, seconds=td.seconds, microseconds=td.microseconds)

def match_season_episode(f):
    @wraps(f)
    def decorator(**kwargs):
        season_slug = kwargs['season']
        episode_slug = kwargs['episode']
        # Locate season
        seasons = [season for season in flask.current_app.library_data
                   if season.slug == season_slug]
        if len(seasons) == 0:
            return http_error(404, 'season \'%s\' not found' % season_slug)
        season = seasons[0]
        # Locate episode
        episodes = [episode for episode in season.episodes
                    if episode.slug == episode_slug]
        if len(episodes) == 0:
            return http_error(404, 'episode \'%s\' not found' % episode_slug)
        episode = episodes[0]
        # Run decorated function
        kwargs.pop('season')
        kwargs.pop('episode')
        return f(season=season, episode=episode, **kwargs)
    return decorator

def episode_has_subtitles(f):
    @wraps(f)
    def decorator(episode, **kwargs):
        if episode.subtitles_path is None:
            return http_error(404, 'subtitles not available for \'%s\'' % episode.name)
        else:
            return f(episode=episode, **kwargs)
    return decorator

def parse_timecode(var):
    def wrapper(f):
        @wraps(f)
        def decorator(episode, **kwargs):
            timecode_in = kwargs[var]
            # Check timecode format
            if not re.match(r'^(\d?\d:)?[0-5]?\d:[0-5]?\d(\.\d\d?\d?)?$', timecode_in):
                return http_error(400, 'invalid timecode format: \'%s\'' % timecode_in)
            # Check it's within bounds of episode
            timecode = Timecode.strftimecode(timecode_in)
            if timecode > episode.duration:
                return http_error(416, 'timecode out of range: \'%s\'' % timecode)
            # Run decorated function
            kwargs[var] = timecode
            return f(episode=episode, **kwargs)
        return decorator
    return wrapper

def check_timecode_range(start_var, end_var, max_length):
    def wrapper(f):
        @wraps(f)
        def decorator(**kwargs):
            start_timecode = kwargs[start_var]
            end_timecode = kwargs[end_var]
            if start_timecode >= end_timecode:
                return http_error(400, 'bad time range')
            elif end_timecode - start_timecode > max_length:
                return http_error(416, 'requested time range exceeds maximum limit')
            else:
                return f(**kwargs)
        return decorator
    return wrapper

def http_error(code, message):
    return flask.Response(message, status=code, mimetype='text/plain')

