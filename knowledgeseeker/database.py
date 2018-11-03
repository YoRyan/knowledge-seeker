import sqlite3
from datetime import timedelta
from pathlib import Path

import cv2
import numpy
from flask import current_app, g

import knowledgeseeker.video as video
from knowledgeseeker.utils import Timecode


FILENAME = 'data.db'


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


def populate(seasons):
    db = get_db()
    cur = db.cursor()
    key = 0
    for season in seasons:
        print('\n%s' % season.name)
        for episode in season.episodes:
            print(' - %s' % episode.name)
            cur.execute(
                'INSERT INTO episode (id, season_slug, episode_slug) ' +
                'VALUES (:id, :season_slug, :episode_slug);',
                { 'id': key, 'season_slug': season.slug,
                  'episode_slug': episode.slug })
            populate_episode(season, episode, key, cur)
            key += 1
            db.commit()


def populate_episode(season, episode, key, cur):
    vidcap = cv2.VideoCapture(str(episode.video_path))
    frames = saved = 0
    last = None
    success, image = vidcap.read()
    while success:
        if last is None or significant_frame(image, last):
            last = image
            saved += 1
            ms = round(vidcap.get(cv2.CAP_PROP_POS_MSEC))

            big_scale = current_app.config['JPEG_VRES']/image.shape[0]
            big_image = cv2.resize(
                image,
                (round(image.shape[1]*big_scale), round(image.shape[0]*big_scale)),
                interpolation=cv2.INTER_AREA)
            big_png = cv2.imencode('.png', big_image)[1].tostring()
            cur.execute(
                'INSERT INTO snapshot (episode_id, ms, png) ' +
                'VALUES (:episode_id, :ms, :png)',
                { 'episode_id': key, 'ms': ms, 'png': sqlite3.Binary(big_png) })

            tiny_scale = current_app.config['JPEG_TINY_VRES']/image.shape[0]
            tiny_image = cv2.resize(
                image,
                (round(image.shape[1]*tiny_scale), round(image.shape[0]*tiny_scale)),
                interpolation=cv2.INTER_AREA)
            tiny_jpg = cv2.imencode('.jpg', tiny_image)[1].tostring()
            cur.execute(
                'INSERT INTO snapshot_tiny (episode_id, ms, jpeg) ' +
                'VALUES (:episode_id, :ms, :jpeg)',
                { 'episode_id': key, 'ms': ms, 'jpeg': sqlite3.Binary(tiny_jpg) })

        frames += 1
        success, image = vidcap.read()
    print('   %d/%d frames (%2.1f%%) saved' % (saved, frames, saved/frames*100.0))


def significant_frame(image, compare_to):
    CHANGE_THRESHOLD = 10
    SIGNIFICANT_P = 0.1
    assert image.shape == compare_to.shape

    diff = cv2.absdiff(image, compare_to)
    flat = numpy.amax(diff, axis=2)
    threshold = numpy.where(flat > CHANGE_THRESHOLD, 1, 0)

    # Debug code to visualize the threshold result.
    #diff_t = numpy.repeat(threshold*255, 3).reshape(
    #    image.shape[0], image.shape[1], 3)
    #cv2.imwrite('diff.png', diff)
    #cv2.imwrite('diff_threshold.png', diff_t)

    changed_px = numpy.count_nonzero(threshold)
    return changed_px >= SIGNIFICANT_P*image.shape[0]*image.shape[1]


def snapshot_times(season_slug, episode_slug):
    cur = get_db().cursor()
    cur.execute('SELECT snapshot.ms FROM episode INNER JOIN snapshot ' +
                'ON episode.id = snapshot.episode_id ' +
                'WHERE episode.season_slug=:season ' +
                '  AND episode.episode_slug=:episode ' +
                'ORDER BY snapshot.ms',
                { 'season': season_slug, 'episode': episode_slug })
    res = cur.fetchall()
    return [row['ms'] for row in res]


def get_full_image(season_slug, episode_slug, ms):
    cur = get_db().cursor()
    cur.execute('SELECT snapshot.png FROM episode INNER JOIN snapshot ' +
                'ON episode.id = snapshot.episode_id ' +
                'WHERE episode.season_slug=:season ' +
                '  AND episode.episode_slug=:episode ' +
                '  AND snapshot.ms=:ms',
                { 'season': season_slug, 'episode': episode_slug, 'ms': ms })
    return cur.fetchone()['png']


def get_tiny_image(season_slug, episode_slug, ms):
    cur = get_db().cursor()
    cur.execute('SELECT snapshot_tiny.jpeg FROM episode INNER JOIN snapshot_tiny ' +
                'ON episode.id = snapshot_tiny.episode_id ' +
                'WHERE episode.season_slug=:season ' +
                '  AND episode.episode_slug=:episode ' +
                '  AND snapshot_tiny.ms=:ms',
                { 'season': season_slug, 'episode': episode_slug, 'ms': ms })
    return cur.fetchone()['jpeg']

