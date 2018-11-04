import ffmpeg
import subprocess
from flask import current_app

from .utils import Timecode

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

def make_gif(video_path, start_time, end_time, vres=360):
    duration = end_time - start_time

    # Get color palette for the highest quality
    pstream = ffmpeg.input(video_path,
                           ss=start_time,
                           t=duration.total_seconds())
    pstream = ffmpeg.filter_(pstream, 'scale', -1, vres)
    pstream = ffmpeg.filter_(pstream, 'palettegen', stats_mode='full')

    # Create the actual jif
    gstream = ffmpeg.input(video_path,
                           ss=start_time)
    gstream = ffmpeg.filter_(gstream, 'scale', -1, vres)
    gstream = ffmpeg_paletteuse_filter(gstream, pstream,
                                       dither='bayer',
                                       bayer_scale=5,
                                       diff_mode='rectangle')
    gstream = ffmpeg.output(gstream, 'pipe:1',
                            format='gif',
                            t=duration.total_seconds(),
                            threads=1)
    return ffmpeg_run_stdout(gstream)

def make_gif_with_subtitles(video_path, subtitle_path, start_time, end_time,
                            vres=360, fonts_path=None, font=None):
    duration = end_time - start_time

    # Get color palette for the highest quality
    pstream = ffmpeg.input(video_path,
                           ss=start_time,
                           t=duration.total_seconds())
    pstream = ffmpeg.filter_(pstream, 'scale', -1, vres)
    pstream = ffmpeg_subtitles_filter(pstream, subtitle_path, start_time,
                                      fonts_path=fonts_path, font=font)
    pstream = ffmpeg.filter_(pstream, 'palettegen', stats_mode='full')

    # Create the actual jif
    gstream = ffmpeg.input(video_path,
                           ss=start_time)
    gstream = ffmpeg.filter_(gstream, 'scale', -1, vres)
    gstream = ffmpeg_subtitles_filter(gstream, subtitle_path, start_time,
                                      fonts_path=fonts_path, font=font)
    gstream = ffmpeg_paletteuse_filter(gstream, pstream,
                                       dither='bayer',
                                       bayer_scale=5,
                                       diff_mode='rectangle')
    gstream = ffmpeg.output(gstream, 'pipe:1',
                            format='gif',
                            t=duration.total_seconds(),
                            threads=1)
    return ffmpeg_run_stdout(gstream)

def make_webm(video_path, start_time, end_time, vres=360):
    duration = end_time - start_time
    stream = ffmpeg.input(video_path,
                          ss=start_time)
    stream = ffmpeg.filter_(stream, 'scale', -1, vres)
    stream = ffmpeg.output(stream, 'pipe:1',
                           **{ 'format': 'webm',
                               't': duration.total_seconds(),
                               'an': None,
                               'sn': None,
                               'c:v': 'libvpx-vp9',
                               'crf': 35,
                               'b:v': '1000k',
                               'cpu-used': 2,
                               'threads': 1 })
    return ffmpeg_run_stdout(stream)

def make_webm_with_subtitles(video_path, subtitle_path, start_time, end_time,
                             vres=360, fonts_path=None, font=None):
    duration = end_time - start_time
    stream = ffmpeg.input(video_path,
                          ss=start_time)
    stream = ffmpeg.filter_(stream, 'scale', -1, vres)
    stream = ffmpeg_subtitles_filter(stream, subtitle_path, start_time,
                                     fonts_path=fonts_path, font=font)
    stream = ffmpeg.output(stream, 'pipe:1',
                           **{ 'format': 'webm',
                               't': duration.total_seconds(),
                               'an': None,
                               'sn': None,
                               'c:v': 'libvpx-vp9',
                               'crf': 35,
                               'b:v': '1000k',
                               'cpu-used': 2,
                               'threads': 1 })
    return ffmpeg_run_stdout(stream)

def video_duration(video_path):
    # https://superuser.com/questions/650291/how-to-get-video-duration-in-seconds
    args = ['-v', 'error', '-show_entries', 'format=duration', '-of',
            'default=noprint_wrappers=1:nokey=1', '-sexagesimal', str(video_path)]
    process = subprocess.run([current_app.config['FFPROBE_PATH']] + args,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode == 0:
        duration = process.stdout.decode('ascii').strip()
        return Timecode.strftimecode(duration)
    else:
        raise FfprobeRuntimeError

def ffmpeg_subtitles_filter(stream, subtitle_path, start_time,
                            fonts_path=None, font=None, font_size=24):
    # Move pointer to start time
    stream = ffmpeg.setpts(stream, 'PTS+%f/TB' % start_time.total_seconds())
    # Add subtitles filter
    sub_kwargs = { 'force_style': 'Fontsize=%d' % font_size }
    if font is not None:
        sub_kwargs['force_style'] += ',FontName=%s' % font
        if fonts_path is not None:
            sub_kwargs['fontsdir'] = fonts_path
    stream = ffmpeg.filter_(stream, 'subtitles', str(subtitle_path), **sub_kwargs)
    # Reset pointer
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
    args = [current_app.config['FFMPEG_PATH']] + args
    if not current_app.config['DEV']:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    else:
        print('\nRunning: %s\n' % ' '.join(args))
        process = subprocess.Popen(args, stdout=subprocess.PIPE)
    return process.stdout

