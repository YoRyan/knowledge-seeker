import flask

def find_episode(season, episode):
    seasons = [s for s in flask.current_app.library_data if s.slug == season]
    if len(seasons) == 0:
        return None, None
    else:
        episodes = [e for e in seasons[0].episodes if e.slug == episode]
        if len(episodes) == 0:
            return None, None
        else:
            return seasons[0], episodes[0]

def http_error(code, message):
    return flask.Response(message, status=code, mimetype='text/plain')

