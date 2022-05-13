import youtube_dl
from subprocess import Popen, PIPE
import re
import datetime


class YT():
    artist = None
    title = None

    def __init__(self, url):
        ydl_opts = {}
        self.url = url
        self.start_time = '00:00:00'
        self.end_time = '00:00:00'
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            self.meta = ydl.extract_info(url, download=False)
            self.streams = {}
            for i in self.meta['formats']:
                self.streams[int(i['format_id'])] = i
            self.video_title = self.meta['title']

    @property
    def tiny_url(self):
        l = []
        for i,j in self.streams.items():
          if j['format_note'] == u'tiny':
            l.append((i,j['filesize']))
        tag, size = max(l, key=lambda x:x[1])
        return self.streams[tag]['url']

    @property
    def ss(self):
        if re.search(r'^[0-5][0-9]:[0-5][0-9]$', self.start_time):
            return f'00:{self.start_time}'
        else:
            return '00:00:00'

    @property
    def t(self):
        if re.search('^[0-5][0-9]:[0-5][0-9]$', self.end_time):
            time = f'00:{self.end_time}'
            t1 = datetime.datetime.strptime(self.ss, '%H:%M:%S')
            t2 = datetime.datetime.strptime(time, '%H:%M:%S')
            delta = t2 - t1
            t0 = datetime.datetime.strptime('00:00:00', '%H:%M:%S')
            return datetime.datetime.strftime(t0 + delta, '%H:%M:%S')
        else:
            return self.duration

    @property
    def duration(self):
        command = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                   '-of', 'default=noprint_wrappers=1:nokey=1', '-sexagesimal',
                   self.tiny_url]
        p = Popen(command, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        if stderr:
            raise Exception(stderr)
        if isinstance(stdout, bytes):
            return stdout.decode().split('.')[0]
        else:
            raise Exception('Could not get duration')

    @property
    def file_name(self):
        return f'{self.artist} - {self.title}.mp3'

    def mp3(self):
        command = ['/opt/telegram/ffmpeg', '-v', 'error', '-i', self.tiny_url, '-vn',
                '-ar', '44100', '-c:a','libmp3lame', '-b:a', '192k', '-ss', self.ss,
                '-t', self.t, '-metadata', f'artist={self.artist}',
                '-metadata', f'title={self.title}', '-f', 'mp3', '-']
        p = Popen(command, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        if stderr:
            raise Exception(stderr)
        return stdout
