import re
import subprocess
from datetime import timedelta

FFMPEG_PATH = 'ffmpeg'
FFPROBE_PATH = 'ffprobe'

class FfmpegRuntimeError(Exception):
    pass

class FfprobeRuntimeError(Exception):
    pass

def strptimecode(td):
    atd = abs(td)
    milliseconds = round(atd.microseconds/1000)
    seconds = atd.seconds % 60
    minutes = atd.seconds // 60 % 60
    hours = atd.seconds // 60 // 60
    string = '%02d:%02d:%02d.%03d' % (hours, minutes, seconds, milliseconds)
    if td >= timedelta(0):
        return string
    else:
        return '-%s' % string

def strftimecode(tc):
    match = re.search(r'^(\d*:)?(\d+):(\d+\.?\d*)$', tc)
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
        raise ValueError('invalid timecode format: \'%s\'' % tc)

def make_snapshot(video_path, time):
    inputs = [(['-ss', strptimecode(time)], _expand(video_path))]
    return run_ffmpeg(inputs, '-vframes', '1', '-f', 'singlejpeg', '-q:v', '1')

def make_snapshot_with_subtitles(video_path, subtitle_path, time,
                                 fonts_path=None, font=None):
    inputs = [(['-ss', strptimecode(time)], _expand(video_path))]
    subtitles_filter = _subtitle_filter(subtitle_path, time, fonts_path, font)
    return run_ffmpeg(inputs, '-vframes', '1', '-f', 'singlejpeg', '-q:v', '1',
                      '-filter_complex', subtitles_filter)

def make_gif(video_path, start_time, end_time, vres=360):
    duration = end_time - start_time

    # Get color palette for the highest quality
    palette_inputs = [(['-ss', strptimecode(start_time), '-t', str(duration.total_seconds())],
                       _expand(video_path))]
    palette_filter = 'scale=-1:%d:lanczos,palettegen=stats_mode=full' % vres
    palette = run_ffmpeg(palette_inputs, '-filter_complex', palette_filter, '-f', 'apng')

    # Create the actual jif
    gif_inputs = [(['-ss', strptimecode(start_time)], _expand(video_path)),
                  (['-f', 'png_pipe'], '-')]
    gif_filter = ('scale=-1:%d:lanczos,paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle' %
                  vres)
    return run_ffmpeg(gif_inputs,
                      '-t', str(duration), '-filter_complex', gif_filter, '-f', 'gif',
                      stdin=palette)

def make_gif_with_subtitles(video_path, subtitle_path, start_time, end_time,
                            vres=360, fonts_path=None, font=None):
    duration = end_time - start_time
    subtitles_filter = _subtitle_filter(subtitle_path, start_time, fonts_path, font)

    # Get color palette for the highest quality
    palette_inputs = [(['-ss', strptimecode(start_time), '-t', str(duration.total_seconds())],
                       _expand(video_path))]
    palette_filter = ('scale=-1:%d:lanczos,palettegen=stats_mode=full,' % vres +
                      subtitles_filter)

    palette = run_ffmpeg(palette_inputs, '-filter_complex', palette_filter, '-f', 'apng')

    # Create the actual jif
    gif_inputs = [(['-ss', strptimecode(start_time)], _expand(video_path)),
                  (['-f', 'png_pipe'], '-')]
    gif_filter = ('scale=-1:%d:lanczos,paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle,' %
                  vres + subtitles_filter)
    return run_ffmpeg(gif_inputs,
                      '-t', str(duration), '-filter_complex', gif_filter, '-f', 'gif',
                      stdin=palette)

def make_webm(video_path, start_time, end_time, vres=360):
    duration = end_time - start_time
    inputs = [(['-ss', strptimecode(start_time)], _expand(video_path))]
    return run_ffmpeg(inputs, '-t', str(duration), '-an', '-sn',
                      '-filter_complex', 'scale=-1:%d' % vres,
                      '-c:v', 'libvpx-vp9', '-crf', '35', '-b:v', '1000k',
                      '-cpu-used', '2', '-f', 'webm')

def make_webm_with_subtitles(video_path, subtitle_path, start_time, end_time,
                             vres=360, fonts_path=None, font=None):
    duration = end_time - start_time
    subtitles_filter = _subtitle_filter(subtitle_path, start_time, fonts_path, font)

    # Create the webm
    inputs = [(['-ss', strptimecode(start_time)], _expand(video_path))]
    webm_filter = 'scale=-1:%d,%s' % (vres, subtitles_filter)
    return run_ffmpeg(inputs, '-t', str(duration), '-an', '-sn', '-filter_complex', webm_filter,
                      '-c:v', 'libvpx-vp9', '-crf', '35', '-b:v', '1000k',
                      '-cpu-used', '2', '-f', 'webm')

"""
def make_preview(video_path, start_timecode, end_timecode):
    duration = end_timecode - start_timecode
    args = ['-ss', str(start_timecode), '-i', video_path, '-t', str(duration),
            '-f', 'webm', '-']
    ffmpeg = subprocess.run([FFMPEG_PATH] + args,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if ffmpeg.returncode == 0:
        return ffmpeg.stdout
    else:
        raise FfmpegRuntimeError
"""

def run_ffmpeg(inputs, *output_args, stdin=None):
    args = (sum([input_args + ['-i', input_file] for input_args, input_file in inputs], []) +
            list(output_args) + ['-'])
    process = subprocess.run([FFMPEG_PATH] + args, input=stdin,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode == 0:
        return process.stdout
    else:
        raise FfmpegRuntimeError

def video_duration(video_path):
    # https://superuser.com/questions/650291/how-to-get-video-duration-in-seconds
    args = ['-v', 'error', '-show_entries', 'format=duration', '-of',
            'default=noprint_wrappers=1:nokey=1', '-sexagesimal', _expand(video_path)]
    process = subprocess.run([FFPROBE_PATH] + args,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode == 0:
        duration = process.stdout.decode('ascii').strip()
        return strftimecode(duration)
    else:
        raise FfprobeRuntimeError

def _subtitle_filter(subtitle_path, start_time, fonts_path=None, font=None):
    f = 'setpts=PTS+%f/TB,subtitles=%s' % (start_time.total_seconds(),
                                           _escape(_expand(subtitle_path)))
    if font is not None:
        f += ':force_style=\'FontName=%s\'' % font
        if fonts_path is not None:
            f += ':fontsdir=%s' % _escape(_expand(fonts_path))
    f += ',setpts=PTS-STARTPTS'
    return f

_expand = lambda path: str(path.absolute())
_escape = lambda path: "'%s'" % path.replace(':', '\\:').replace("'", "'\\\\\\''")

