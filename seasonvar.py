from urllib.request import Request, urlopen
import re
from base64 import b64decode
import codecs


class Seasonvar():
    def __init__(self, url):
        self.html, headers = self.get_content(url)
        self.ref = url
        self.cookie = headers.get('set-cookie')
        self.x_requested_with = 'XMLHttpRequest'

    def get_content(self, url, ref=None, cookie=None, data=None, x_requested_with=None):
        request = Request(url)
        request.add_data(data)
        request.add_header('Accept', '*/*')
        request.add_header('Accept-Language', 'uk-UA,uk')
        request.add_header('User-Agent', 'Mozilla/5.0 (Linux; Android 6.0;\
                            Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, \
                            like Gecko) Chrome/73.0.3683.86 Mobile Safari/537.36')
        request.add_header('Referer', ref)
        request.add_header('Cookie', cookie)
        request.add_header('Host', 'seasonvar.ru')
        request.add_header('Origin', 'http://seasonvar.ru')
        request.add_header('X-Requested-With', x_requested_with)
        response = urlopen(request, timeout = 10)
        return response.read(), response.headers.dict

    @property
    def video_url(self):
        id = re.search('data-id-season="(\d*)"', self.html).group(1)
        serial = re.search('data-id-serial="(\d*)"', self.html).group(1)
        secure = re.search('\'secureMark\': \'(.*)\'', self.html).group(1)
        time = re.search('\'time\': (\d*)', self.html).group(1)

        data = 'id={}&serial={}&type=html5&secure={}&time={}'.format(id, serial, secure, time)

        player, header = self.get_content(
            'http://seasonvar.ru/player.php',
            ref=self.ref, cookie=self.cookie, data=data,
            x_requested_with=self.x_requested_with
        )

        playls2 = re.findall('"(/playls2/.+?)"', player)
        plist = []

        for item in playls2:
            playls2_url = 'http://seasonvar.ru' + item
            plist_content, header = self.get_content(playls2_url)

            for i in eval(plist_content):
                url = re.sub('(\\\\/\\\\/.*?=)', '', i['file'])
                url = b64decode(url[2:])
                title = i['title'].replace('<br>', '').replace('\/', ' ')
                title = codecs.unicode_escape_decode(title)[0]
                title = title.encode('utf-8')
                plist.append((url, title))

        return plist
