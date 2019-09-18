# Knowledge Seeker

A television episode browser inspired by [Frinkiac](https://frinkiac.com). This
one just happens to be configured for all three seasons of Avatar: the Last
Airbender, one of the greatest American cartoons of all time. A public instance
of Knowledge Seeker is accessible at [atla.pictures](https://atla.pictures).

Like Frinkiac, KS indexes episodes by their plain text subtitles, and attempts
to determine which frames are "most significant" by examining the differences
in the color values of the pixels. Unlike Frinkiac, KS is open source and was
written in Python by a bored and nostalgic college kid.

Knowledge Seeker is a CGI program built on Python 3 and Flask. It uses NumPy to
read video files, and (of course) ffmpeg to transcode them to GIF animations.

## Setup

1. Install KS with pip as you would any ordinary Python package.
2. Configuration takes place within the Flask app
   [instance folder](https://flask.palletsprojects.com/en/master/config/#instance-folders)
   (henceforth referred to as $INSTANCE), the precise location of which depends
   on wherever pip installed the package. To locate this, you could simply run
   the app with `FLASK_APP=knowledgeseeker flask run`, and look for the
   inevitable failure to read the configuration file.
3. All parameters are stored in $INSTANCE/config.py. sample_config.py contains
   representative values and some documentation. All paths are relative to
   $INSTANCE.
4. config.py points to the library file, which is a JSON metadata collection of
   all episodes and seasons. Seasons are defined by a brief slug, a proper
   name, (optionally) a path to an icon, and a list of episodes. Episodes are
   defined by a slug, a name, a video file, and a subtitle file. Video files
   must be in a format readable by NumPy and Ffmpeg; anecdotally, the x264 codec
   seems to strike a good balance between storage requirements and transcode
   speed. Subtitles must be in srt format. All paths are relative to the
   directory containing the library file (henceforth referred to as $LIBRARY).
5. With the necessary data in the proper locations, use
   `FLASK_APP=knowledgeseeker flask read-library` to build the massive database
   of episodes and snapshots. (This takes a very long time.)
6. Use `FLASK_APP=knowledgeseeker FLASK_ENV=development flask run` to run the
   app in debug mode with Flask's built-in Werkzeug server. For production, use
   the
   [recommended configuration](https://flask.palletsprojects.com/en/master/tutorial/deploy/#run-with-a-production-server)
   for Flask apps: a WSGI server to run the app behind a hardened reverse
   proxy.
