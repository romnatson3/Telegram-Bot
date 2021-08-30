from urllib.request import urlopen
import re
import codecs
import json

class Kinovod(object):
    def __init__(self, url_main):
        self.url_main = url_main
        self.html = self.__get_content(url_main)
        self.type = re.search(r'var MOVIE_TYPE = "(.+)";', self.html).group(1)

    def __get_content(self, url):
        response = urlopen(url)
        if response.code == 200:
            r = response.read().decode('utf-8')
            return r
        else:
            return None

    @property
    def title(self):
        regex = re.compile(r'<title>(.*)</title>')
        result = regex.search(self.html)
        title = result.group(1)
        return title

    def __values(self, var_name):
        var_name = var_name.upper()
        regex = re.compile(r'var\s%s\s=\s(.*);' % (var_name))
        result = regex.search(self.html)
        if result:
            string = result.group(1)
            d = {'\'': '', '\"': ''}
            r = re.compile('|'.join(d.keys()))
            return r.sub(lambda x: d[x.group()], string)

    @property
    def _video_file(self):
        site = re.search(r'https://.+?/', self.url_main).group()
        player_type = 'new'
        file_type = 'mp4'
#        file_type = 'hls'
        movie_id = self.__values('movie_id')
        identifier = self.__values('identifier')
        st = self.__values('vod_hash')
        e = self.__values('vod_time')
        url = '%svod/%s?identifier=%s&player_type=%s&file_type=%s&st=%s&e=%s' \
            % (site, movie_id, identifier, player_type, file_type, st, e)
        return self.__get_content(url).split('|')[1]


    def _url_title_list(self, s, title=None):
        l = []
        regex = re.compile(r'\[(\d+p)\](http.+?)(?=\s|$)')
        for i in s.split(','):
            result = regex.findall(i)
            if result:
                t = '{} ({})'.format(title, result[0][0])
                l.append((result[0][1], t))
            else:
                regex2 = re.compile(r'(\[(\d+p)\])?\{(.*)\}(http.+?)(?=\s|$)')
                for j in i.split(';'):
                    result2 = regex2.findall(j)
                    if result2:
                        t = '{} ({}, {})'.format(title, result2[0][2], result2[0][1])
                        l.append((result2[0][3], t))
        return l


    @property
    def video_url(self):
        if self.type == 'films':
            return self._url_title_list(self._video_file, self.title)
        else:
            l = []
            s = json.loads(self._video_file)
            for season in s:
                if season.get('playlist'):
                    for episode in season['playlist']:
                        t = '{} | {}'.format(season['comment'], episode['comment'])
                        l.extend(self._url_title_list(episode['file'], t))
                else:
                    t = season['comment']
                    l.extend(self._url_title_list(season['file'], t))
            return l

    @property
    def list_serials_files(self):
        if self.type == 'serials':
            s = json.loads(self._video_file)
            if s[0].get('playlist'):
                return s
