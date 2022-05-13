from flask import Flask, request, send_from_directory
import re
from subprocess import Popen, PIPE
import json
import pickle
from PIL import Image
import sys
import os
from io import StringIO, BytesIO
from kinovod import Kinovod
from kinotochka import Kinotochka
from seasonvar import Seasonvar
from parcels import Parcels, get_parcel_info_and_save, get_data_from_parcel_db, delete_parcel, parcel_name_add, second_track
from yt import YT
from send import send
from logger import logger
import httplib2
from settings import TOKEN, ALLOWED_ID, STATIC_FILE, KODI_PLAYLIST
from multiprocessing import Process
import shutil
import requests
from bs4 import BeautifulSoup


class Dot(dict):
    def __init__(self, d):
        for i in d.copy():
            if i == 'from':
                i = 'From'
                d[i] = d.pop('from')
            if i == 'photo':
                d[i] = d[i][-1]
            if isinstance(d[i], dict):
                self.__dict__[i] = Dot(d[i])
                self[i] = d[i]
            else:
                self.__dict__[i] = d[i]
                self[i] = d[i]

    def __getattr__(self, name):
        self.__dict__.get(name)

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __iter__(self):
        return self.__dict__.iteritems()


def print_exception():
    file_line_list=[]
    s = ''
    def line(trac):
        if trac:
            file_name = re.search(r'file \'(.+?)\'', trac.tb_frame.__str__()).group(1)
            line_no = str(trac.tb_lineno)
            file_line_list.append((file_name, line_no))
            trac = trac.tb_next
            line(trac)
    exc, trac = sys.exc_info()[1:]
    line(trac)
    for i in file_line_list[::-1]:
        s += f'File {i[0]}, line {i[1]}\n'
    except_type = re.split(r'\(', exc.__repr__(), 1)[0]
    s += f'{except_type}: {exc.args[0]}'
    return s


def http_request(url):
    http = httplib2.Http()
    headers, content = http.request(url)
    return headers, content


def recovery_object(id):
    if os.path.exists(str(id)):
        with open(f'{id}', 'rb') as f:
            return pickle.load(f)


def save_object(id, obj):
    with open(f'{id}', 'wb') as f:
        pickle.dump(obj, f)


def video_url(m):
    l = []
    y = recovery_object(m.From.id)
    for i in y.streams:
        if y.streams[i].get('filesize'):
            size = round(y.streams[i]['filesize'] / 2**20, 2)
        else:
            size = None
        name = f'{i} - {y.streams[i]["format_note"]} {y.streams[i]["ext"]} {size} Mb'
        send('sendMessage', chat_id=m.From.id, parse_mode='HTML',
             text=f'<a href="{y.streams[i]["url"]}">{name}</a>')
        l.append((y.streams[i]['url'], name))
    kodi(l, 'films')


def video_18(m):
    y = recovery_object(m.From.id)
    url = y.streams[18]['url']
    h = httplib2.Http()
    h, c = h.request(url)
    path = os.path.join(STATIC_FILE, 'video.mp4')
    with open(path, 'bw') as f:
        f.write(c)
    send('sendMessage', chat_id=m.From.id, parse_mode='HTML',
            text=f'<a href="https://rns.pp.ua/telegram_webhook/file/video.mp4">{y.video_title}</a>')


def download_mp3(m):
    y = recovery_object(m.From.id)
    mp3_string = y.mp3()
    headers, content = send('sendAudio', multipart=True, chat_id=m.From.id,
                            audio=mp3_string, caption=y.file_name)


def pdf_to_jpg(m):
    if m.document:
        if m.document.mime_type in ['application/pdf', 'application/wps-office.pdf']:
            headers, content = send('getFile', file_id=m.document.file_id)
            if content['ok']:
                file_url = f'https://api.telegram.org/file/bot{TOKEN}/{content["result"]["file_path"]}'
                headers, content = http_request(file_url)
                path = os.path.join(STATIC_FILE, 'video.mp4')
                with open(path, 'wb') as pdf:
                    pdf.write(content)
                    regex = re.compile(b'/Type\s*/Page([^s]|$)', re.MULTILINE|re.DOTALL)
                    r = regex.findall(content)
                    pages = range(len(r) + 1)[1:]

                for i in pages:
                    command = ['gs', '-dQUIET', '-dBATCH', '-dNOPAUSE', '-dSAFER',
                               '-sDEVICE=png16m', '-r300', f'-dFirstPage={i}',
                               f'-dLastPage={i}', '-sOutputFile=%stdout', path]
                    p = Popen(command, stdout=PIPE, stderr=PIPE)
                    stdout, stderr = p.communicate()

                    caption = f'{m.document.file_name[:-4]}_{i}.png'
                    logger.info(caption)
#                    headers, content = send('sendPhoto', multipart=True, 
#                                chat_id=m.From.id, photo=stdout, caption=caption)
                    headers, content = send('sendDocument', multipart=True,
                            chat_id=m.From.id, document=stdout, caption=caption)


def save_jpg(m):
    if m.document:
        if m.document.mime_type in ['image/jpeg', 'image/png']:
            headers, content = send('getFile', file_id=m.document.file_id)
            caption = m.document.file_name[:-3] + 'pdf'
    if m.photo:
        headers, content = send('getFile', file_id=m.photo.file_id)
        caption = 'document.pdf'
    if content:
        if content['ok']:
            file_url = f'https://api.telegram.org/file/bot{TOKEN}/{content["result"]["file_path"]}'
            headers, content = http_request(file_url)
            input_file = BytesIO(content)
            try:
                l = recovery_object(m.From.id)
                l.append(input_file)
                save_object(m.From.id, l)
            except:
                save_object(m.From.id, [caption, input_file])

            send('deleteMessage', chat_id=m.From.id, message_id=message_dict.get(m.From.id))

            inline_keyboard_markup = {
                    'inline_keyboard': [[{'text': 'OK', 'callback_data': 'convert_to_pdf'}]]
                    }
            header, content = send('sendMessage', chat_id=m.From.id, parse_mode='HTML',
                                   text=f'<b>Конвертувати в PDF</b>',
                                   reply_markup=json.dumps(inline_keyboard_markup))
            message_dict[m.From.id] = content['result']['message_id']


def convert_to_pdf(m):
    if os.path.exists(f'{m.From.id}'):
        output_file = BytesIO()
        l = recovery_object(m.From.id)
        caption = l[0]
        im1 = Image.open(l[1])
        im_list =  map(lambda x: Image.open(x), l[2:])
        im1.save(output_file, "PDF", resolution=100.0, save_all=True, append_images=im_list)
        output_file.seek(0)
        output_file = output_file.read()
        headers, content = send('sendDocument', multipart=True, chat_id=m.From.id,
                document=output_file, caption=caption)
        os.remove(m.From.id)


def kodi(video_url, video_type):
    m3u = os.path.join(STATIC_FILE, 'playlist.m3u')
    dst = os.path.join(KODI_PLAYLIST, 'playlist.m3u')
    open(m3u, 'w').close()
    with open(m3u, 'w') as m3u_file:
        m3u_file.write('#EXTM3U\n')
        for i in video_url:
            if video_type == 'films':
                m3u_file.write(f'#EXTINF:0, {i[1]}\n{i[0]}\n')

            elif video_type == 'serials':
                season_episode = i[1].split('|')
                url = i[0].replace("\\","")
                if len(season_episode) == 1:
                    m3u_file.write(f'#EXTINF:0 group-title="1 сезон", \
                            {season_episode[0].strip()}\n{url}\n')
                else:
                    m3u_file.write(f'#EXTINF:0 group-title="{season_episode[0].strip()}", \
                            {season_episode[1].strip()}\n{url}\n')
    shutil.copy(m3u, dst)


def film_serial(m, callback_data=None):
    video_url = None
    video_type = None

    if callback_data:
        v = recovery_object(m.From.id)
        for season in v.list_serials_files:
            if season['comment'] == callback_data:
                for episode in season['playlist']:
                    for i in episode['file'].split(','):
                        result = re.findall(r'\[(\d+p)](http.+?)(?=\s|$)', i)
                        if result:
                            title =  f'{season["comment"]} | {episode["comment"]} ({result[0][0]})'
                            send('sendMessage', chat_id=m.From.id, parse_mode='HTML',
                                 text=f'<a href="{result[0][1]}">{title}</a>')
        return

    regex_kinovod = re.compile('http.?://kinovod.(net|cc)/(film|serial)/[\w|-]+')
    regex_kinotochka = re.compile('https://kinotochka.co/[\d|\w|-]+.html')
    regex_seasonvar = re.compile('http://seasonvar.ru/[\d|\w|-]+.html')
    kinovod_url = regex_kinovod.search(m.text)
    kinotochka_url = regex_kinotochka.search(m.text)
    seasonvar_url = regex_seasonvar.search(m.text)

    if kinovod_url:
        v = Kinovod(kinovod_url.group())
        video_type = v.type
        video_url = v.video_url
        if v.list_serials_files:
            l = []
            for season in v.list_serials_files:
                l.append([dict(text=season['comment'], callback_data=season['comment'])])
            inline_keyboard_markup = {'inline_keyboard': l}
            headers, content = send('sendMessage', chat_id=m.From.id, text=v.title,
                                    reply_markup=json.dumps(inline_keyboard_markup))
            save_object(m.From.id, v)
            kodi(video_url, video_type)
            return

    elif kinotochka_url:
        v = Kinotochka(kinotochka_url.group())
        video_type = 'films'
        video_url = v.video_url

    elif seasonvar_url:
        v = Seasonvar(seasonvar_url.group())
        video_type = 'serials'
        video_url = v.video_url

    if video_url:
        kodi(video_url, video_type)
        for i in video_url:
            send('sendMessage', chat_id=m.From.id, parse_mode='HTML',
                 text=f'<a href="{i[0]}">{i[1]}</a>')


def youtube(m):
    y = YT(m.text)
    save_object(m.From.id, y)
    l = [[{'text': '\U000027A1', 'callback_data': 'start'},
         {'text': '\U00002B05', 'callback_data': 'end'},
         {'text': '\U0001F399', 'callback_data': 'artist'},
         {'text': '\U0001F3BC', 'callback_data': 'title'},
         {'text': '\U00002B07', 'callback_data': 'download'},
         {'text': '\U0001F517', 'callback_data': 'url'},
         {'text': '\U0001F3A5', 'callback_data': '18'}]]
    inline_keyboard_markup = {'inline_keyboard': l}
    send('sendMessage', chat_id=m.From.id, parse_mode='HTML',
         text=f'<b>{y.video_title}</b>',
         reply_markup=json.dumps(inline_keyboard_markup))


def exchange_rates(ID):
    response = requests.get('https://minfin.com.ua/ua/currency/drogobych/usd/')
    html = BeautifulSoup(response.text)
    head = html.find('h1', class_='bottom-head').text
    table = html.find(class_='table-response mfm-table mfcur-table-lg mfcur-table-lg-currency-cur has-no-tfoot')
    buy_td = table.findAll('td')[5]
    buy_title = buy_td.attrs['data-title']
    buy = re.search(r'\n([0-9,.]*)\n', buy_td.text).group(1)
    buy_int = round(float(buy), 2)
    selling_td = table.findAll('td')[6]
    selling_title = selling_td.attrs['data-title']
    selling = re.search(r'\n([0-9,.]*)\n', selling_td.text).group(1)
    selling_int = round(float(selling), 2)
    text = f'<b>{head}</b>\n{buy_title}: <b>{buy_int}</b>\n{selling_title}: <b>{selling_int}</b>'
    send('sendMessage', chat_id=ID, parse_mode='HTML', text=text)


pattern = dict(
        parcels = r'^[A-Za-z0-9]{13,17}',
        parcel_name = r'^name_[A-Za-z0-9]{13,17}',
        parcel_delete = r'^delete_[A-Za-z0-9]{13,17}',
        youtube = r'^(https://www\.youtube\.com/watch\?v=\S{11})|(https://youtu\.be/\S{11})',
        kinovod = r'http.?://kinovod.(net|cc)/(film|serial)/[\w|-]+',
        kinotochka = r'https://kinotochka.co/[\d|\w|-]+.html',
        seasonvar = r'http://seasonvar.ru/[\d|\w|-]+.html',
        convert_to_pdf = r'^convert_to_pdf$',
        start = r'^start$',
        end = r'^end$',
        artist = r'^artist$',
        title = r'^title$',
        download = r'^download$',
        video_18 = r'^18$',
        url = r'^url$',
        season = r'^\d{1,2}\sсезон$'
)


app = Flask(__name__)

@app.route('/telegram_webhook/file/<filename>', methods=['GET'])
def file(filename):
    return send_from_directory(STATIC_FILE, filename)


@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    global message_dict
    try:
        if request.method == 'POST':
            m = Dot(request.json)
            m = m.message if m.message else m.callback_query
            logger.info(f'INCOMING MESSAGE: {m}\n')

            if m.From.id in ALLOWED_ID:
                ID = m.From.id
                previous_message = message_dict.get(ID)
                if m.text or m.data:
                    TEXT = m.text if m.text else m.data
                    message_dict[ID] = TEXT

                if m.text == '/parcels':
                    get_data_from_parcel_db(ID)
                    return 'ok', 200

                if m.text == '/second_track':
                    second_track(ID)
                    return 'ok', 200

                if m.text == '/exchange_rates':
                    exchange_rates(ID)
                    return 'ok', 200

                if m.text:
                    if previous_message in ['start', 'end', 'title', 'artist']:
                        y = recovery_object(ID)
                        if previous_message == 'title':
                            y.title = m.text
                            logger.info(f'add title tag: {y.title}')
                        elif previous_message == 'artist':
                            y.artist = m.text
                            logger.info(f'add artist tag: {y.artist}')
                        elif previous_message == 'start':
                            y.start_time = m.text
                            logger.info(f'set start time:{y.start_time}')
                        elif previous_message == 'end':
                            y.end_time = m.text
                            logger.info(f'set end time: {y.end_time}')
                        save_object(ID, y)

                    if previous_message:
                        result_parcel_name = re.search(pattern['parcel_name'], previous_message)
                        if result_parcel_name:
                            parcel_id = previous_message[5:]
                            parcel_name_add(ID, parcel_id, TEXT)
                            return 'ok', 200

                if m.text or m.data:
                    for i in pattern:
                        regex = re.compile(pattern[i])
                        result = regex.search(TEXT)
                        if result:
                            if i == 'parcels':
                                parcel_proc = Process(target=get_parcel_info_and_save, args=(ID, TEXT))
                                parcel_proc.start()
                            elif i == 'youtube':
                                youtube(m)
                            elif i in ['kinovod', 'kinotochka', 'seasonvar']:
                                film_serial(m)
                            elif i == 'parcel_name':
                                send('sendMessage', chat_id=ID, text='Відправ назву відстеження')
                            elif i == 'parcel_delete':
                                delete_parcel(ID, TEXT)
                            elif i == 'convert_to_pdf':
                                convert_to_pdf(m)
                            elif i == 'start':
                                send('sendMessage', chat_id=ID, text='Час початку пісні. Наприклад: 01:12')
                            elif i == 'end':
                                send('sendMessage', chat_id=ID, text='Час закінчення пісні. Наприклад: 07:53')
                            elif i == 'title':
                                send('sendMessage', chat_id=ID, text='Назва пісні')
                            elif i == 'artist':
                                send('sendMessage', chat_id=ID, text='Виконавець')
                            elif i == 'download':
                                yt_proc = Process(target=download_mp3, args=(m,))
                                yt_proc.start()
                            elif i == 'url':
                                video_url(m)
                            elif i == 'video_18':
                                yt_proc = Process(target=video_18, args=(m,))
                                yt_proc.start()
                            elif i == 'season':
                                film_serial(m, TEXT)
                    return 'ok', 200

                if m.photo:
                    save_jpg(m)
                    return 'ok', 200

                if m.document:
                    pdf_to_jpg(m)
                    return 'ok', 200

    except:
        logger.error(print_exception())
    return 'ok', 200

if __name__ == '__main__':
#    app.run(host='rns.pp.ua', port='443', ssl_context=('/opt/telegram/public.pem', '/opt/telegram/private.key'), debug=True)
    message_dict = {}
    app.run(host='10.8.0.13', port='80', debug=True)
