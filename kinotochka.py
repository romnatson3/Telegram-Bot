from subprocess import Popen, PIPE
import re


class Kinotochka():
    def __init__(self, url):
        self.html = self._curl(url)[0].decode('utf-8')

    def _curl(self, url):
        command = ['curl', '--connect-timeout', '10', url]
        p = Popen(command, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        return stdout, stderr

    @property
    def video_url(self):
        title = re.search('title>(.*)</title', self.html).group(1)
        serial = re.search('https://kinotochka.co/.+?/.+?/.*txt', self.html)
        if serial:
            self.text, headers = self._curl(serial.group())
            l = re.findall('"comment":"(.+?)<br>.*","file":"(.+?)"', self.text.decode())
            l2 = []
            for i in l:
                l2.append((self.repl_quality(i[1]), title + ' ' + i[0]))
            return l2

        film = re.search('Playerjs\(.*file:"(.+?)"', self.html)
        if film:
            l = []
            for i in film.group(1).split(',', 1):
                l.append((i.replace(',', ''), title))
            return l

    def repl_quality(self, url):
        r = re.search('(\[(\d+),(\d+)\])\.mp4', url)
        if r:
            return url.replace(r.group(1), r.group(2))
        else:
            return url
