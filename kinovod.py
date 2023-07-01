import json
from seleniumwire import webdriver
import re
import requests
import os
import shutil
from tempfile import mkdtemp


class Kinovod(object):
    def __init__(self, url_main):
        self.url_main = url_main
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--incognito')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        user_data_dir = mkdtemp()
        chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(self.url_main)
        self.html = driver.page_source
        identifier = re.search(r'var IDENTIFIER = "(.+?)"', self.html).group(1)
        self.type = re.search(r'var MOVIE_TYPE = "(.+?)"', self.html).group(1)
        for request in driver.requests:
            if identifier in request.url and request.url.startswith('https://kinovod.net/vod/'):
                self.file_url = request.url.replace('hls', 'mp4')
        driver.quit()
        shutil.rmtree(user_data_dir, ignore_errors=True)

    def _get_content(self, url):
        response = requests.get(url)
        if response.status_code == 200:
            return response.text

    @property
    def _video_file(self):
        content = self._get_content(self.file_url)
        content = content.split('|')[1]
        return content

    def _url_title_list(self, s, second_title):
        l = []
        regex = re.compile(r'\[(\d+p)\](http.+?)(?=\s|$)')
        for i in s.split(','):
            result = regex.findall(i)
            if result:
                if second_title:
                    t = '{} ({}) - {}'.format(self.title, result[0][0], second_title)
                else:
                    t = '{} ({})'.format(self.title, result[0][0])
                t = t.replace(' смотреть онлайн', '')
                l.append((result[0][1].replace('\\', ''), t))
            else:
                regex2 = re.compile(r'(\[(\d+p)\])?\{(.*)\}(http.+?)(?=\s|$)')
                for j in i.split(';'):
                    result2 = regex2.findall(j)
                    if result2:
                        t = '{} ({}, {})'.format(self.title, result2[0][2], result2[0][1])
                        t = t.replace(' смотреть онлайн', '')
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
        l = []
        if self.type == 'films':
            try:
                s = json.loads(self._video_file)
            except json.decoder.JSONDecodeError:
                s = [{'file': self._video_file, 'title': ''}]
            for i in s:
                l.extend(self._url_title_list(i['file'], i['title']))
        else:
            s = json.loads(self._video_file)
            if s[0].get('folder'):
                for season in s:
                    for episode in season['folder']:
                        t = '{} | {}'.format(season['title'], episode['title'])
                        l.extend(self._url_title_list(episode['file'], t))
            else:
                for episode in s:
                    l.extend(self._url_title_list(episode['file'], episode['title']))
        return l

    @property
    def list_serials_files(self):
        if self.type == 'serials':
            s = json.loads(self._video_file)
            if s[0].get('folder'):
                return [i['title'] for i in s]
