import flask
import re
from datetime import datetime, timedelta
from functools import wraps
from time import mktime
from wsgiref.handlers import format_date_time

class Timecode(timedelta):
    def __str__(self):
        av = abs(self)
        total_ms = round(av.microseconds/1000 + av.seconds*1000)
        milliseconds = total_ms % 1000
        seconds = total_ms // 1000 % 60
        minutes = total_ms // 1000 // 60 % 60
        hours = total_ms // 1000 // 60 // 60
        if hours > 0:
            string = '%02d:%02d:%02d.%03d' % (hours, minutes, seconds, milliseconds)
        else:
            string = '%02d:%02d.%03d' % (minutes, seconds, milliseconds)
        if self >= timedelta(0):
            return string
        else:
            return '-%s' % string
    def __add__(self, other):
        return Timecode.from_timedelta(timedelta.__add__(self, other))
    def __sub__(self, other):
        return Timecode.from_timedelta(timedelta.__sub__(self, other))
    def __mul__(self, other):
        return Timecode.from_timedelta(timedelta.__mul__(self, other))
    def __truediv__(self, other):
        return Timecode.from_timedelta(timedelta.__truediv__(self, other))
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
    def str_seconds(self):
        s = self.total_seconds()
        hours = s // 60 // 60
        minutes = s // 60 % 60
        seconds = s % 60
        if hours > 0:
            return '%d:%02d:%02d' % (hours, minutes, seconds)
        else:
            return '%d:%02d' % (minutes, seconds)
    def from_timedelta(td):
        return Timecode(days=td.days, seconds=td.seconds, microseconds=td.microseconds)

def match_season(f):
    @wraps(f)
    def decorator(**kwargs):
        season_slug = kwargs['season']
        seasons = [season for season in flask.current_app.library_data
                   if season.slug == season_slug]
        if len(seasons) == 0:
            flask.abort(404, 'season \'%s\' not found' % season_slug)
        season = seasons[0]
        kwargs.pop('season')
        return f(season=season, **kwargs)
    return decorator

def match_season_episode(f):
    @wraps(f)
    @match_season
    def decorator(**kwargs):
        season = kwargs['season']
        episode_slug = kwargs['episode']
        episodes = [episode for episode in season.episodes
                    if episode.slug == episode_slug]
        if len(episodes) == 0:
            flask.abort(404, 'episode \'%s\' not found' % episode_slug)
        episode = episodes[0]
        kwargs.pop('episode')
        return f(episode=episode, **kwargs)
    return decorator

def episode_has_subtitles(f):
    @wraps(f)
    def decorator(episode, **kwargs):
        if episode.subtitles_path is None:
            flask.abort(404, 'subtitles not available for \'%s\'' % episode.name)
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
                flask.abort(400, 'invalid timecode format: \'%s\'' % timecode_in)
            # Check it's within bounds of episode
            timecode = Timecode.strftimecode(timecode_in)
            if timecode > episode.duration:
                flask.abort(416, 'timecode out of range: \'%s\'' % timecode)
            # Run decorated function
            kwargs[var] = timecode
            return f(episode=episode, **kwargs)
        return decorator
    return wrapper

def check_timecode_range(start_var, end_var, get_max_length):
    def wrapper(f):
        @wraps(f)
        def decorator(**kwargs):
            start_timecode = kwargs[start_var]
            end_timecode = kwargs[end_var]
            # NOTE: bad hack to avoid querying the config outside of the
            # application context
            max_length = get_max_length()
            if start_timecode >= end_timecode:
                flask.abort(400, 'bad time range')
            elif end_timecode - start_timecode > max_length:
                flask.abort(416, 'requested time range exceeds maximum limit')
            else:
                return f(**kwargs)
        return decorator
    return wrapper

def set_expires(f):
    @wraps(f)
    def decorator(**kwargs):
        response = f(**kwargs)
        date = datetime.now() + flask.current_app.config['HTTP_CACHE_EXPIRES']
        response.headers.set('Expires', format_date_time(mktime(date.timetuple())))
        return response
    return decorator

def static_cached(f):
    @wraps(f)
    def decorator(**kwargs):
        cached = flask.current_app.static_cache.serve(flask.request.endpoint, **kwargs)
        if cached is not None:
            return cached
        else:
            return f(**kwargs)
    return decorator

