import re
import subprocess

FFMPEG_PATH = 'ffmpeg'
FFPROBE_PATH = 'ffprobe'

class FfmpegRuntimeError(Exception):
    pass

class FfprobeRuntimeError(Exception):
    pass

class Timecode(object):
    # HH:MM:SS:ZZZ
    def __init__(self, milliseconds=0):
        self.value = milliseconds
    def seconds(self):
        return self.value / 1000
    def __repr__(self):
        milliseconds = abs(self.value) % 1000
        seconds = abs(self.value) // 1000 % 60
        minutes = abs(self.value) // 1000 // 60 % 60
        hours = abs(self.value) // 1000 // 60 // 60
        string = '%02d:%02d:%02d.%03d' % (hours, minutes, seconds, milliseconds)
        if self.value >= 0:
            return string
        else:
            return '-' + string
    def __str__(self):
        return self.__repr__()
    def __eq__(self, other):
        return self.value == other.value
    def __add__(self, other):
        return Timecode(self.value + other.value)
    def __sub__(self, other):
        return Timecode(self.value - other.value)
    def __gt__(self, other):
        return self.value > other.value
    def __ge__(self, other):
        return self > other or self == other
    def __lt__(self, other):
        return self.value < other.value
    def __le__(self, other):
        return self < other or self == other
    def __abs__(self):
        return Timecode(abs(self.value))

    def strftimecode(string):
        match = re.search(r'^(\d*:)?(\d+):(\d+\.?\d*)$', string)
        if match is not None:
            groups = match.groups()
            if groups[0] is None:
                hours = 0
            else:
                hours = int(groups[0][:-1])
            minutes = int(groups[1])
            milliseconds = round(float(groups[2])*1000)
            return Timecode(hours*60*60*1000 + minutes*60*1000 + milliseconds)
        else:
            raise ValueError('invalid timecode format: \'%s\'' % string)

def make_snapshot(video_path, timecode):
    inputs = [(['-ss', str(timecode)], str(video_path.absolute()))]
    return run_ffmpeg(inputs, ['-vframes', '1', '-f', 'singlejpeg', '-q:v', '1'])

def make_snapshot_with_subtitles(video_path, subtitle_path, timecode,
                                 fonts_path=None, font=None):
    inputs = [(['-ss', str(timecode)], str(video_path.absolute()))]

    # Filter for subtitles
    subtitles_filter = 'subtitles=\'%s\'' % str(subtitle_path.absolute())
    if font is not None:
        subtitles_filter += ':force_style=\'FontName=%s\'' % font
        if fonts_path is not None:
            subtitles_filter += ':fontsdir=%s' % fonts_path

    ff_filter = ('setpts=PTS+%f/TB,%s,setpts=PTS-STARTPTS' %
                 (timecode.seconds(), subtitles_filter))
    return run_ffmpeg(inputs, ['-vframes', '1', '-f', 'singlejpeg', '-q:v', '1',
                               '-filter_complex', ff_filter])

def make_gif(video_path, start_timecode, end_timecode, vres=360):
    duration = end_timecode - start_timecode

    # Get color palette for the highest quality
    palette_inputs = [(['-ss', str(start_timecode), '-t', str(duration.seconds())],
                       str(video_path.absolute()))]
    palette_filter = 'scale=-1:%d:lanczos,palettegen=stats_mode=full' % vres
    palette = run_ffmpeg(palette_inputs, ['-filter_complex', palette_filter, '-f', 'apng'])

    # Create the actual jif
    gif_inputs = [(['-ss', str(start_timecode)], str(video_path.absolute())),
                  (['-f', 'png_pipe'], '-')]
    gif_filter = ('scale=-1:%d:' % vres +
                  'lanczos,paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle')
    return run_ffmpeg(gif_inputs, ['-t', str(duration),
                                   '-filter_complex', gif_filter, '-f', 'gif'],
                      stdin=palette)

def make_gif_with_subtitles(video_path, subtitle_path, start_timecode, end_timecode,
                            vres=360, fonts_path=None, font=None):
    duration = end_timecode - start_timecode

    # Filter for subtitles
    subtitles_filter = 'subtitles=\'%s\'' % str(subtitle_path.absolute())
    if font is not None:
        subtitles_filter += ':force_style=\'FontName=%s\'' % font
        if fonts_path is not None:
            subtitles_filter += ':fontsdir=%s' % fonts_path
    subtitles_filter += ',setpts=PTS-STARTPTS'

    # Get color palette for the highest quality
    palette_inputs = [(['-ss', str(start_timecode), '-t', str(duration.seconds())],
                       str(video_path.absolute()))]
    palette_filter = ('scale=-1:%d:' % vres +
                      'lanczos,palettegen=stats_mode=full,setpts=PTS+%f/TB,%s' %
                      (start_timecode.seconds(), subtitles_filter))

    palette = run_ffmpeg(palette_inputs, ['-filter_complex', palette_filter,
                                          '-f', 'apng'])

    # Create the actual jif
    gif_inputs = [(['-ss', str(start_timecode)], str(video_path.absolute())),
                  (['-f', 'png_pipe'], '-')]
    gif_filter = ('scale=-1:%d:' % vres +
                  'lanczos,paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle,' +
                  'setpts=PTS+%f/TB,%s,setpts=PTS-STARTPTS' %
                  (start_timecode.seconds(), subtitles_filter))
    return run_ffmpeg(gif_inputs, ['-t', str(duration), '-filter_complex', gif_filter,
                                   '-f', 'gif'],
                      stdin=palette)

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

def run_ffmpeg(inputs, output_args, stdin=None):
    args = (sum([input_args + ['-i', input_file] for input_args, input_file in inputs], []) +
            output_args + ['-'])
    process = subprocess.run([FFMPEG_PATH] + args, input=stdin,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode == 0:
        return process.stdout
    else:
        raise FfmpegRuntimeError

def video_duration(video_path):
    # https://superuser.com/questions/650291/how-to-get-video-duration-in-seconds
    args = ['-v', 'error', '-show_entries', 'format=duration', '-of',
            'default=noprint_wrappers=1:nokey=1', '-sexagesimal', str(video_path.absolute())]
    process = subprocess.run([FFPROBE_PATH] + args,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode == 0:
        duration = process.stdout.decode('ascii').strip()
        return Timecode.strftimecode(duration)
    else:
        raise FfprobeRuntimeError

