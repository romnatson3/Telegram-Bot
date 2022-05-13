import httplib2
from urllib.parse import urlencode
import requests
import json
from logger import logger
import random
from io import StringIO, BytesIO
from settings import TOKEN


def get_boundary():
    l = []
    for i in range(31):
        l.append(random.choice('abcdefghijklmnopqrstuvwxyz0123456789'))
    return ''.join(l)


def get_form_data(data, boundary):
    form_data = BytesIO()
    form_data.write(bytes(f'--{boundary}\r\n', encoding='utf-8'))
    form_data.write(bytes(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n', encoding='utf-8'))
    form_data.write(bytes(f'{data["chat_id"]}\r\n', encoding='utf-8'))
    form_data.write(bytes(f'--{boundary}\r\n', encoding='utf-8'))
    form_data.write(bytes(f'Content-Disposition: form-data; name="{data["type"]}"; filename="{data["caption"]}"\r\n\r\n', encoding='utf-8'))
    form_data.write(data['file'])
    form_data.write(bytes('\r\n', encoding='utf-8'))
    form_data.write(bytes(f'--{boundary}--', encoding='utf-8'))
    form_data.seek(0,0)
    return form_data.read()


def send(method, multipart=None, **data):
    http = httplib2.Http()
    URL = f'https://api.telegram.org/bot{TOKEN}/{method}'
    headers = {}
    if not multipart:
        body = urlencode(data)
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    else:
        boundary = get_boundary()
        if data.get('video'):
            data['type'] = 'video'
            data['file'] = data['video']
        if data.get('audio'):
            data['type'] = 'audio'
            data['file'] = data['audio']
        if data.get('photo'):
            data['type'] = 'photo'
            data['file'] = data['photo']
        if data.get('document'):
            data['type'] = 'document'
            data['file'] = data['document']
        body = get_form_data(data, boundary)
        headers['Content-Length'] = str(len(body))
        headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
    header, content = http.request(URL, method='POST', body=body, headers=headers)
    if content:
        content = json.loads(content.decode('utf-8'))
        logger.info(f'BOT RESPONSE: {content}\n')
        return header, content
    else:
        logger.info(f'BOT RESPONSE: None')
        return None, None

#def send(method, multipart=None, **data):
#    URL = f'https://api.telegram.org/bot{TOKEN}/{method}'
#    headers = {}
#    if not multipart:
#        response = requests.post(URL, data=data)
#    else:
#        if data.get('audio'):
#            files = {'audio': data.pop('audio')}
#        if data.get('photo'):
#            files = {'photo': data.pop('photo')}
#        if data.get('document'):
#            files = {'document': data.pop('document')}
#        response = requests.post(URL, data=data, files=files)
#    return response.headers, response.content


