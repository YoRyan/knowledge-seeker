import sqlite3
from pathlib import Path

import cv2
import numpy
from flask import current_app, g

from knowledgeseeker.utils import dt_milliseconds, strip_html


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


def populate(library_data):
    db = get_db()
    cur = db.cursor()
    season_key = episode_key = 0
    for season in library_data:
        print('\n%s' % season.name)
        cur.execute(
            'INSERT INTO season (id, slug, icon_png, name) '
            '       VALUES (:id, :slug, :icon_png, :name)',
            { 'id': season_key,
              'slug': season.slug,
              'icon_png': season.icon,
              'name': season.name })
        for episode in season.episodes:
            print(' - %s' % episode.name)
            cur.execute(
                'INSERT INTO episode (id, slug, name, duration, '
                '                     video_path, season_id) '
                '       VALUES (:id, :slug, :name, :duration, '
                '               :video_path, :season_id)',
                { 'id': episode_key,
                  'slug': episode.slug,
                  'name': episode.name,
                  'duration': episode.duration.milliseconds,
                  'video_path': str(episode.video_path),
                  'season_id': season_key })
            populate_episode(episode, episode_key, cur)
            populate_subtitles(episode, episode_key, cur)
            episode_key += 1
            db.commit()
        season_key += 1


def populate_episode(episode, key, cur):
    # Locate and save significant frames.
    vidcap = cv2.VideoCapture(str(episode.video_path))
    frames = saved = ms = 0
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
                'INSERT INTO snapshot (episode_id, ms, png) '
                '       VALUES (:episode_id, :ms, :png)',
                { 'episode_id': key, 'ms': ms, 'png': sqlite3.Binary(big_png) })

            tiny_scale = current_app.config['JPEG_TINY_VRES']/image.shape[0]
            tiny_image = cv2.resize(
                image,
                (round(image.shape[1]*tiny_scale), round(image.shape[0]*tiny_scale)),
                interpolation=cv2.INTER_AREA)
            tiny_jpg = cv2.imencode('.jpg', tiny_image)[1].tostring()
            cur.execute(
                'INSERT INTO snapshot_tiny (episode_id, ms, jpeg) '
                '       VALUES (:episode_id, :ms, :jpeg)',
                { 'episode_id': key, 'ms': ms, 'jpeg': sqlite3.Binary(tiny_jpg) })

        frames += 1
        success, image = vidcap.read()

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

    print('   %d/%d frames (%2.1f%%) saved' % (saved, frames, saved/frames*100.0))


def populate_subtitles(episode, key, cur):
    for sub in episode.subtitles:
        start_ms = dt_milliseconds(sub.start)
        end_ms = dt_milliseconds(sub.end)
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


def init_app(app):
    @app.teardown_appcontext
    def close_db(*args, **kwargs):
        return close_connection(*args, **kwargs)

