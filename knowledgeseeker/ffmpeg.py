import subprocess

import ffmpeg
from flask import current_app


class FfmpegRuntimeError(Exception):
    pass


class FfprobeRuntimeError(Exception):
    pass


def make_snapshot(video_path, time, vres=720):
    stream = (ffmpeg
              .input(video_path,
                     ss=time)
              .filter_('scale', -1, vres, flags='fast_bilinear')
              .output('pipe:1',
                      format='apng',
                      vframes=1,
                      q=1,
                      threads=1))
    return ffmpeg_run_stdout(stream)


def make_snapshot_with_subtitles(video_path, subtitle_path, time,
                                 fonts_path=None, font=None):
    stream = ffmpeg.input(video_path,
                          ss=time)
    stream = ffmpeg_subtitles_filter(stream, subtitle_path, time,
                                     fonts_path=fonts_path, font=font)
    stream = ffmpeg.output(stream, 'pipe:1',
                           format='singlejpeg',
                           vframes=1,
                           q=1,
                           threads=1)
    return ffmpeg_run_stdout(stream)


def make_tiny_snapshot(video_path, time, vres=100):
    stream = (ffmpeg
              .input(video_path,
                     ss=time)
              .filter_('scale', -1, vres, flags='fast_bilinear')
              .output('pipe:1',
                      format='singlejpeg',
                      vframes=1,
                      q=5,
                      threads=1))
    return ffmpeg_run_stdout(stream)


def make_gif(video_path, start_ms, end_ms):
    start_s = str(start_ms/1000)
    end_s = str(end_ms/1000)
    duration = str((end_ms - start_ms)/1000)
    vres=current_app.config.get('GIF_VRES')

    # Get color palette for the highest quality
    pstream = ffmpeg.input(video_path, ss=start_s, t=duration)
    pstream = ffmpeg.filter_(pstream, 'scale', -1, vres)
    pstream = ffmpeg.filter_(pstream, 'palettegen', stats_mode='full')

    # Create the actual jif
    gstream = ffmpeg.input(video_path, ss=start_s)
    gstream = ffmpeg.filter_(gstream, 'scale', -1, vres)
    gstream = ffmpeg_paletteuse_filter(gstream, pstream,
                                       dither='bayer',
                                       bayer_scale=5,
                                       diff_mode='rectangle')
    gstream = ffmpeg.output(gstream, 'pipe:1', format='gif', t=duration, threads=1)
    return ffmpeg_run_stdout(gstream)


def make_gif_with_subtitles(video_path, subtitle_path, start_ms, end_ms):
    start_s = str(start_ms/1000)
    end_s = str(end_ms/1000)
    duration = str((end_ms - start_ms)/1000)
    vres=current_app.config.get('GIF_VRES')

    # Get color palette for the highest quality
    pstream = ffmpeg.input(video_path, ss=start_s, t=duration)
    pstream = ffmpeg.filter_(pstream, 'scale', -1, vres)
    pstream = ffmpeg_subtitles_filter(pstream, subtitle_path, start_ms)
    pstream = ffmpeg.filter_(pstream, 'palettegen', stats_mode='full')

    # Create the actual jif
    gstream = ffmpeg.input(video_path, ss=start_s)
    gstream = ffmpeg.filter_(gstream, 'scale', -1, vres)
    gstream = ffmpeg_subtitles_filter(gstream, subtitle_path, start_ms)
    gstream = ffmpeg_paletteuse_filter(gstream, pstream, dither='bayer',
                                       bayer_scale=5, diff_mode='rectangle')
    gstream = ffmpeg.output(gstream, 'pipe:1', format='gif', t=duration, threads=1)
    return ffmpeg_run_stdout(gstream)


def make_webm(video_path, start_ms, end_ms):
    start_s = str(start_ms/1000)
    end_s = str(end_ms/1000)
    duration = str((end_ms - start_ms)/1000)
    vres=current_app.config.get('WEBM_VRES')

    stream = ffmpeg.input(video_path, ss=start_s)
    stream = ffmpeg.filter_(stream, 'scale', -1, vres)
    stream = ffmpeg.output(stream, 'pipe:1',
                           **{ 'format': 'webm',
                               't': duration,
                               'an': None,
                               'sn': None,
                               'c:v': 'libvpx-vp9',
                               'crf': 35,
                               'b:v': '1000k',
                               'cpu-used': 2,
                               'threads': 1 })
    return ffmpeg_run_stdout(stream)


def make_webm_with_subtitles(video_path, subtitle_path, start_ms, end_ms):
    start_s = str(start_ms/1000)
    end_s = str(end_ms/1000)
    duration = str((end_ms - start_ms)/1000)
    vres=current_app.config.get('WEBM_VRES')

    stream = ffmpeg.input(video_path, ss=start_s)
    stream = ffmpeg.filter_(stream, 'scale', -1, vres)
    stream = ffmpeg_subtitles_filter(stream, subtitle_path, start_ms)
    stream = ffmpeg.output(stream, 'pipe:1',
                           **{ 'format': 'webm',
                               't': duration,
                               'an': None,
                               'sn': None,
                               'c:v': 'libvpx-vp9',
                               'crf': 35,
                               'b:v': '1000k',
                               'cpu-used': 2,
                               'threads': 1 })
    return ffmpeg_run_stdout(stream)


def ffmpeg_subtitles_filter(stream, subtitle_path, start_ms):
    font_dir = current_app.config.get('FF_FONT_DIR', None)
    font_name = current_app.config.get('FF_FONT_NAME', None)
    font_size = current_app.config.get('FF_FONT_SIZE', 24)

    stream = ffmpeg.setpts(stream, 'PTS+%f/TB' % (start_ms/1000))
    sargs = { 'force_style': 'Fontsize=%d' % font_size }
    if font_dir is not None:
        sargs['fontsdir'] = str(font_dir)
    if font_name is not None:
        sargs['force_style'] += ',FontName=%s' % font_name
    stream = ffmpeg.filter_(stream, 'subtitles', str(subtitle_path), **sargs)
    stream = ffmpeg.setpts(stream, 'PTS-STARTPTS')
    return stream


def ffmpeg_paletteuse_filter(video_stream, palette_stream, **kwargs):
    # https://github.com/kkroening/ffmpeg-python/issues/73
    node = ffmpeg.nodes.FilterNode([video_stream, palette_stream], 'paletteuse',
                                   max_inputs=2, kwargs=kwargs)
    return node.stream()


def ffmpeg_run_stdout(stream):
    # NOTE: nasty workaround for bad escaping by ffmpeg-python
    args = [str(a)
            .replace('\\\\\\\\\\\\\\', '\\\\\\')
            .replace('\\\\\\\\\\\\', '\\\\\\')
            for a in stream.get_args()]
    args = [current_app.config.get('FFMPEG_PATH')] + args
    if not current_app.config.get('DEV'):
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    else:
        print('\nRunning: %s\n' % ' '.join(args))
        process = subprocess.Popen(args, stdout=subprocess.PIPE)
    return process.stdout

