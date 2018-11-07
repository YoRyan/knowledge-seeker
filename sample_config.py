from datetime import timedelta
from pathlib import Path


LIBRARY = Path('library/atla.json')

JPEG_VRES = 720
JPEG_TINY_VRES = 100
PIL_FONT = Path('library/fonts/Herculanum.wolff')
PIL_FONT_SIZE = 60
PIL_MAXWIDTH = 30

FFMPEG_PATH = 'ffmpeg'
FFPROBE_PATH = 'ffprobe'

GIF_VRES = 360
WEBM_VRES = 480
MAX_GIF_LENGTH = timedelta(seconds=10)
MAX_WEBM_LENGTH = timedelta(seconds=15)
FF_FONT_DIR = Path('library/fonts/')
FF_FONT_NAME = 'Herculanum'
FF_FONT_SIZE = 24

HTTP_CACHE_EXPIRES = timedelta(days=7)
