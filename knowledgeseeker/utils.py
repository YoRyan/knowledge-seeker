import re
from datetime import datetime, timedelta
from functools import wraps
from time import mktime

from flask import current_app
from wsgiref.handlers import format_date_time


def strptimecode(s):
    match = re.search(r'^(\d*:)?(\d+):(\d+\.?\d*)$', s)
    if match is not None:
        groups = match.groups()
        if groups[0] is None:
            hours = 0
        else:
            hours = int(groups[0][:-1])
        minutes = int(groups[1])
        milliseconds = round(float(groups[2])*1000)
        return timedelta(hours=hours, minutes=minutes, milliseconds=milliseconds)
    else:
        raise ValueError('invalid timecode format: \'%s\'' % s)


def strftimecode(td):
    s = td.total_seconds()
    hours = s // 60 // 60
    minutes = s // 60 % 60
    seconds = s % 60
    if hours > 0:
        return '%d:%02d:%02d' % (hours, minutes, seconds)
    else:
        return '%d:%02d' % (minutes, seconds)


def set_expires(f):
    @wraps(f)
    def decorator(**kwargs):
        response = f(**kwargs)
        date = datetime.now() + current_app.config.get('HTTP_CACHE_EXPIRES')
        response.headers.set('Expires', format_date_time(mktime(date.timetuple())))
        return response
    return decorator


def strip_html(s):
    return re.sub(r'</?[^>]+>', '', s)

