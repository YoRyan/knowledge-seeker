import os
import sqlite3
from concurrent.futures import as_completed, ThreadPoolExecutor
from datetime import datetime
from functools import wraps
from pathlib import Path

import cv2
import numpy
from flask import abort, current_app, g

from knowledgeseeker.utils import strip_html


FILENAME = 'data.db'
POPULATE_WORKERS = int(os.environ.get('POPULATE_WORKERS', os.cpu_count()))


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        path = Path(current_app.instance_path)/FILENAME
        c = sqlite3.connect(str(path))
        c.row_factory = sqlite3.Row
        db = g._database = c
    return db


def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def remove():
    path = Path(current_app.instance_path)/FILENAME
    if path.exists():
        path.unlink()


def match_season(f):
    @wraps(f)
    def decorator(season, **kwargs):
        cur = get_db().cursor()
        cur.execute('SELECT id FROM season WHERE slug=:season_slug',
                    { 'season_slug': season })
        res = cur.fetchone()
        if res is None:
            abort(404, 'season not found')
        return f(season_id=res['id'], **kwargs)
    return decorator


def match_episode(f):
    @wraps(f)
    def decorator(season, episode, **kwargs):
        cur = get_db().cursor()
        cur.execute('PRAGMA full_column_names = ON')
        cur.execute(
            'SELECT episode.id, season.id FROM '
            '    season '
            '    INNER JOIN episode ON episode.season_id = season.id '
            ' WHERE season.slug=:season_slug AND episode.slug=:episode_slug',
            { 'season_slug': season, 'episode_slug': episode })
        res = cur.fetchone()
        cur.execute('PRAGMA full_column_names = OFF')
        if res is None:
            abort(404, 'episode not found')
        return f(season_id=res['season.id'], episode_id=res['episode.id'], **kwargs)
    return decorator


def populate(library_data):
    # check_same_thread needed to allow threads to access tables not created
    # by themselves (I like to live dangerously).
    db = sqlite3.connect(str(Path(current_app.instance_path)/FILENAME),
                         check_same_thread=False)
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    season_key = episode_key = 0
    episodes = {}
    for season in library_data:
        cur.execute(
            'INSERT INTO season (id, slug, icon_png, name) '
            '       VALUES (:id, :slug, :icon_png, :name)',
            { 'id': season_key,
              'slug': season.slug,
              'icon_png': season.icon,
              'name': season.name })
        for episode in season.episodes:
            cur.execute(
                'INSERT INTO episode (id, slug, name, duration, '
                '                     video_path, subtitles_path, season_id) '
                '       VALUES (:id, :slug, :name, :duration, '
                '               :video_path, :subtitles_path, :season_id)',
                { 'id': episode_key,
                  'slug': episode.slug,
                  'name': episode.name,
                  'duration': 0,
                  'video_path': str(episode.video_path),
                  'subtitles_path': str(episode.subtitles_path),
                  'season_id': season_key })
            episodes[episode_key] = episode
            episode_key += 1
        season_key += 1
    db.commit()

    config = { 'full_vres': current_app.config['JPEG_VRES'],
               'tiny_vres': current_app.config['JPEG_TINY_VRES'] }
    def fill(key):
        cursor = db.cursor()
        episode = episodes[key]
        saved, frames = populate_episode(episode, key, cursor, **config)
        populate_subtitles(episode, key, cursor)
        return ('%s - %d/%d frames (%.1f%%) saved'
                % (episode.name, saved, frames, saved/frames*100.0))
    with ThreadPoolExecutor(max_workers=POPULATE_WORKERS) as executor:
        for res in executor.map(fill, episodes.keys()):
            print(' * %s' % res)
    db.commit()


def populate_episode(episode, key, cur, full_vres=720, tiny_vres=100):
    # Locate and save significant frames.
    vidcap = cv2.VideoCapture(str(episode.video_path))
    frames = saved = ms = 0
    classifier = FrameClassifier()
    success, image = vidcap.read()
    while success:
        ms = round(vidcap.get(cv2.CAP_PROP_POS_MSEC))
        if classifier.classify(image, ms):
            saved += 1

            big_scale = full_vres/image.shape[0]
            big_image = cv2.resize(
                image,
                (round(image.shape[1]*big_scale), round(image.shape[0]*big_scale)),
                interpolation=cv2.INTER_AREA)
            big_png = cv2.imencode('.png', big_image)[1].tostring()
            cur.execute(
                'INSERT OR IGNORE INTO snapshot (episode_id, ms, png) '
                '       VALUES (:episode_id, :ms, :png)',
                { 'episode_id': key, 'ms': ms, 'png': sqlite3.Binary(big_png) })

            tiny_scale = tiny_vres/image.shape[0]
            tiny_image = cv2.resize(
                image,
                (round(image.shape[1]*tiny_scale), round(image.shape[0]*tiny_scale)),
                interpolation=cv2.INTER_AREA)
            tiny_jpg = cv2.imencode('.jpg', tiny_image)[1].tostring()
            cur.execute(
                'INSERT OR IGNORE INTO snapshot_tiny (episode_id, ms, jpeg) '
                '       VALUES (:episode_id, :ms, :jpeg)',
                { 'episode_id': key, 'ms': ms, 'jpeg': sqlite3.Binary(tiny_jpg) })
        frames += 1
        success, image = vidcap.read()

    # Set the episode's duration.
    cur.execute('UPDATE episode SET duration=:ms WHERE id=:id',
                { 'id': key, 'ms': ms })

    # Set the episode's preview frame.
    cur.execute(
        '  SELECT ms FROM snapshot '
        '   WHERE episode_id=:episode_id '
        'ORDER BY ABS(ms-:target) ASC LIMIT 1',
        { 'episode_id': key, 'target': round(ms/2) })
    res = cur.fetchone()
    if res is not None:
        cur.execute(
            'UPDATE episode SET snapshot_ms=:snapshot_ms WHERE id=:id',
            { 'id': key, 'snapshot_ms': res['ms'] })

    return saved, frames


class FrameClassifier(object):

    TRANS_THRESHOLD = 90.0
    TARGET_FPS = 5.0

    def __init__(self):
        self._last = self._saved = None

    def classify(self, image, ms):
        # - Save all hard transitions (color difference > TRANS_THRESHOLD).
        # - Save at least 3 images per second, but only if there isn't a long
        #   period of duplicate frames.
        if self._last is None:
            self._last = (image, ms)
            save = True
        else:
            last_image, last_ms = self._last
            saved_image, saved_ms = self._saved

            last_color = numpy.average(last_image, axis=(0, 1))
            this_color = numpy.average(image, axis=(0, 1))
            color_diff = numpy.sum(abs(last_color - this_color))
            if color_diff > FrameClassifier.TRANS_THRESHOLD:
                #cv2.imwrite('classify_last.png', last_image)
                #cv2.imwrite('classify_next.png', image)
                #input('transition detected at %d' % ms)
                save = True
            elif (ms - saved_ms >= 1000/FrameClassifier.TARGET_FPS
                  and color_diff > 0.1):
                save = True
            else:
                save = False
        self._last = (image, ms)
        if save:
            self._saved = (image, ms)
        return save


def populate_subtitles(episode, key, cur):
    for sub in episode.subtitles:
        start_ms = sub.start.total_seconds()*1000
        end_ms = sub.end.total_seconds()*1000
        cur.execute(
            'SELECT ms FROM snapshot '
            '       WHERE episode_id=:episode_id '
            '             AND ms>=:start_ms AND ms<=:end_ms '
            'ORDER BY ms',
            { 'episode_id': key, 'start_ms': start_ms, 'end_ms': end_ms })
        snapshot_ms = next(map(lambda row: row['ms'], cur.fetchall()), None)
        cur.execute(
            'INSERT INTO subtitle (episode_id, idx, content, '
            '                      start_ms, end_ms, snapshot_ms) '
            '       VALUES (:episode_id, :idx, :content, '
            '               :start_ms, :end_ms, :snapshot_ms)',
            { 'episode_id': key, 'content': sub.content, 'idx': sub.index,
              'start_ms': start_ms, 'end_ms': end_ms, 'snapshot_ms': snapshot_ms })
        if snapshot_ms is not None:
            cur.execute(
                'INSERT INTO subtitle_search (episode_id, snapshot_ms, content) '
                '       VALUES (:episode_id, :snapshot_ms, :content)',
                { 'episode_id': key, 'snapshot_ms': snapshot_ms,
                  'content': strip_html(sub.content) })


def init_app(app):
    @app.teardown_appcontext
    def close_db(*args, **kwargs):
        return close_connection(*args, **kwargs)

