from datetime import timedelta
from pathlib import Path

#
# All paths are relative to the instance folder.
#

## All episodes, their video files, and their subtitle files.
LIBRARY = Path('library/atla.json')

## Jpeg snapshots and subtitling.
JPEG_VRES = 720
JPEG_TINY_VRES = 100
# Path to a font acceptable to Pillow.
PIL_FONT = Path('library/fonts/Herculanum.wolff')
PIL_FONT_SIZE = 60
PIL_MAXWIDTH = 30

## Paths to ffmpeg binaries.
FFMPEG_PATH = 'ffmpeg'
FFPROBE_PATH = 'ffprobe'

## Webm/Gif animations and subtitling.
GIF_VRES = 360
WEBM_VRES = 480
MAX_GIF_LENGTH = timedelta(seconds=10)
MAX_WEBM_LENGTH = timedelta(seconds=15)
# Ffmpeg requires a path to the directory containing your desired font...
FF_FONT_DIR = Path('library/fonts/')
# ...and its filename, without the extension.
FF_FONT_NAME = 'Herculanum'
FF_FONT_SIZE = 24

## Server options.
HTTP_CACHE_EXPIRES = timedelta(days=7)
