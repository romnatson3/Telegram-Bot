import json
from selenium import webdriver
import pychrome
import re
import urllib
import os


class Kinovod(object):
    def __init__(self, url_main):
        self.url_main = url_main
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--enable-automation')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--remote-debugging-port=8000')
        driver = webdriver.Chrome(executable_path='/usr/bin/chromedriver', options=chrome_options)
        browser = pychrome.Browser(url="http://127.0.0.1:8000")
        tab = browser.list_tab()[0]
        tab.set_listener("Network.requestWillBeSent", self._request_will_be_sent)
        tab.start()
        tab.call_method("Network.enable")
        driver.get(url_main)
        tab.wait(1)
        self.html = driver.page_source
        self.type = re.search(r'var MOVIE_TYPE = "(.+)";', self.html).group(1)
        tab.stop()
        driver.quit()
        os.system("killall chromium-browser")
        os.system("find /tmp -name '.org.chrom*' -exec rm -fr {} \;")

    def _request_will_be_sent(self, **kwargs):
        url = kwargs.get('request').get('url')
        result = re.search(r'^(?P<begin>.+)\?identifier=(?P<identifier>.+)&player_type=(?P<player_type>.+)&file_type=(?P<file_type>.+)&st=(?P<st>.+)&e=(?P<e>.+)&_=(?P<_>.+)$', url)
        if result:
            file_url_dict = result.groupdict()
            begin_url = file_url_dict.pop('begin')
            file_url_dict['player_type'] = 'new'
            file_url_dict['file_type'] = 'mp4'
            self.file_url = f'{begin_url}?{urllib.parse.urlencode(file_url_dict)}'

    def _get_content(self, url):
        response = urllib.request.urlopen(url)
        if response.status == 200:
            return response.read()

    @property
    def _video_file(self):
        content = self._get_content(self.file_url)
        content = content.decode('unicode-escape').split('|')[1]
        return content

    def _url_title_list(self, s, title=None):
        l = []
        regex = re.compile(r'\[(\d+p)\](http.+?)(?=\s|$)')
        for i in s.split(','):
            result = regex.findall(i)
            if result:
                t = '{} ({})'.format(title, result[0][0])
                l.append((result[0][1].replace('\\', ''), t))
            else:
                regex2 = re.compile(r'(\[(\d+p)\])?\{(.*)\}(http.+?)(?=\s|$)')
                for j in i.split(';'):
                    result2 = regex2.findall(j)
                    if result2:
                        t = '{} ({}, {})'.format(title, result2[0][2], result2[0][1])
                        l.append((result2[0][3].replace('\\', ''), t))
        return l

    @property
    def title(self):
        regex = re.compile(r'<title>(.*)</title>')
        result = regex.search(self.html)
        title = result.group(1)
        return title

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
