import re
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import io
from time import sleep
import sqlite3
from send import send
import json
from logger import logger
from settings import SELENIUM_RUN_TYPE
import os
from datetime import datetime


class Parcels():
    def __init__(self, parcel_id, selenium_run_type):
        self.parcel_id = parcel_id
        self.selenium_run_type = selenium_run_type
        self.session_id = self._open_selenium_session()

    def _open_selenium_session(self):
        if self.selenium_run_type == 'remote':
            proxy = '127.0.0.1:12345'
            cap = DesiredCapabilities.FIREFOX
            cap['proxy']= {
                'proxyType': 'MANUAL',
                'httpProxy': proxy,
                'ftpProxy': proxy,
                'sslProxy': proxy
                }
            self.driver = webdriver.Remote(command_executor='http://10.8.0.2:4444/wd/hub', desired_capabilities=cap)
        elif self.selenium_run_type == 'local':
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--enable-automation')
            chrome_options.add_argument('--no-sandbox')
            self.driver = webdriver.Chrome(executable_path='/usr/bin/chromedriver', options=chrome_options)
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """

                        Object.defineProperty(window, 'navigator', {
                            value: new Proxy(navigator, {
                            has: (target, key) => (key === 'webdriver' ? false : key in target),
                            get: (target, key) =>
                                key === 'webdriver'
                                ? undefined
                                : typeof target[key] === 'function'
                                ? target[key].bind(target)
                                : target[key]
                            })
                        });
                        console.log = console.dir = console.error = function(){};
                    """
                },
            )
        return self.driver.session_id

    def get_page_source(self):
        URL = 'https://parcelsapp.com/tracking/'
        self.driver.get('{}{}'.format(URL, self.parcel_id))
        WebDriverWait(self.driver, 60).until(EC.presence_of_all_elements_located((By.XPATH, "//section[@class='tracking-info']")))
        self.content = self.driver.page_source
        self.driver.quit()
        if self.selenium_run_type == 'local':
            os.system("killall chromium-browser")
            os.system("find /tmp -name '.org.chrom*' -exec rm -fr {} \;")

    @property
    def event_list(self):
        event_list = []
        for i in self.content.split('\n\n'):
            regex = re.compile(r'<strong>(.*)</strong>[\s\S]*<span>(.*)</span>[\s\S]*<strong>(.*)</strong>[\s\S]*</div>\n\s*([\w\s]*)\n\s*</div>')
            result = regex.findall(i)
            if result:
                event_list.append(result[0])
        event_list = list(map(lambda x:('{} {}, {}'.format(x[0],x[1], x[-1]), *x[2:-1]) ,event_list))
        event_list.reverse()
        if not event_list:
            regex = re.compile(r'<div class="event-time">[\s\S]*<strong>(.*)</strong>[\s\S]*<strong>(.*)</strong>')
            result = regex.findall(self.content)
            if result:
                event_list = result
        return event_list

    @property
    def event_list_html(self):
        s = io.StringIO()
        for i in self.event_list:
            s.write('<i>{}</i>\n{}\n'.format(*i))
        s.seek(0)
        return s.read()

    @property
    def parcel_attributes(self):
        parcel_attributes = []
        regex = re.compile(r'<table class="parcel-attributes">[\s\S]+?<tbody>([\s\S]+?)</tbody>')
        result = regex.search(self.content)
        if result:
            regex = re.compile('<td>(?P<name>.*)</td>[\s\S]+?<span>(?P<value>.*)</span>')
            table = result.group(1)
            for i in table.split('<tr>'):
                row = regex.search(i)
                if row:
                    parcel_attributes.append((row.group('name'), row.group('value')))
        return parcel_attributes

    @property
    def parcel_attributes_html(self):
        s = io.StringIO()
        if self.parcel_attributes:
            for i in self.parcel_attributes:
                s.write('<i>{}</i>: {}\n'.format(*i))
            s.seek(0)
        return s.read()


def get_parcel_info_and_save(id, text):
    try:
        parcel_id, parcel_name = text.split(' ', 1)
    except:
        parcel_id = text
        parcel_name = None
    result = re.search(r'^[A-Za-z0-9]{13,17}', parcel_id)
    if result:
        conn = sqlite3.connect('parcels.db')
        cursor = conn.cursor()
        cursor.execute(f'select id,name,date from parcels where id="{parcel_id}" and user_id="{id}";')
        select_result = cursor.fetchall()
        if select_result:
            parcel_name = select_result[0][1]
            time = time_on_the_road(select_result[0][2])
            parcel = Parcels(parcel_id, SELENIUM_RUN_TYPE)
            parcel.get_page_source()
            send('sendMessage', chat_id=id, parse_mode='HTML',
                 text=f'<b>{parcel_name}</b>{time}\n{parcel.parcel_attributes_html}{parcel.event_list_html}')
            logger.info(f'get {parcel_id} info')
        else:
            date = datetime.now().strftime('%d.%m.%Y %H:%M')
            cursor.execute(f'insert into parcels (id,name,user_id,date) \
                                values("{parcel_id}","{parcel_name}","{id}","{date}");')
            conn.commit()
            conn.close()
            logger.info(f'save parcel {parcel_id}')
            parcel = Parcels(parcel_id, SELENIUM_RUN_TYPE)
            parcel.get_page_source()
            if parcel_name:
                send('sendMessage', chat_id=id, parse_mode='HTML',
                     text=f'<b>{parcel_name}</b>\n{parcel.parcel_attributes_html}{parcel.event_list_html}')
            else:
                name_callback_data = f'name_{parcel_id}'
                l = [[{'text': "Додати ім'я", 'callback_data': name_callback_data}]]
                inline_keyboard_markup = {'inline_keyboard': l}
                send('sendMessage', chat_id=id, parse_mode='HTML',
                     text=f'{parcel.parcel_attributes_html}{parcel.event_list_html}',
                     reply_markup=json.dumps(inline_keyboard_markup))
            logger.info(f'get {parcel_id} info')
    else:
        logger.info(f'dont match parcel {parcel_id}')
        send('sendMessage', chat_id=id, text='Провір номер відстеження')


def get_data_from_parcel_db(id):
    conn = sqlite3.connect('parcels.db')
    cursor = conn.cursor()
    cursor.execute(f'select id,name,date from parcels where user_id="{id}";')
    result = cursor.fetchall()
    if result:
        for i in result:
            parcel_id = f'{i[0]}'
            delete_callback_data = f'delete_{i[0]}'
            if i[1] != 'None':
                l = [[dict(text=parcel_id, callback_data=parcel_id),
                    dict(text='\U0001F5D1',callback_data=delete_callback_data)]]
            else:
                name_callback_data = f'name_{i[0]}'
                l = [[dict(text=parcel_id, callback_data=parcel_id),
                    dict(text='\U0001F5D1',callback_data=delete_callback_data),
                    dict(text="Додати ім'я",callback_data=name_callback_data)]]
            inline_keyboard_markup = {'inline_keyboard': l}
            time = time_on_the_road(i[2])
            send('sendMessage', chat_id=id, parse_mode='HTML',
                 text=f'<b>{i[1]}</b>{time}', reply_markup=json.dumps(inline_keyboard_markup))
    else:
        send('sendMessage', chat_id=id, text='Відправ номер відстеження і через пробіл назву')
    conn.close()


def time_on_the_road(date):
    now = datetime.now()
    add_date = datetime.strptime(date, '%d.%m.%Y %H:%M')
    diff = now - add_date
    return f', днів в дорозі: {diff.days}'


def delete_parcel(id, text):
    parcel_id = text[7:]
    conn = sqlite3.connect('parcels.db')
    cursor = conn.cursor()
    cursor.execute(f'delete from parcels where id="{parcel_id}" and user_id="{id}";')
    conn.commit()
    conn.close()
    send('sendMessage', chat_id=id, text=f'Відстеження {parcel_id} видалено')


def parcel_name_add(id, parcel_id, text):
    conn = sqlite3.connect('parcels.db')
    cursor = conn.cursor()
    cursor.execute(f'update parcels set name="{text}" where id="{parcel_id}" and user_id="{id}";')
    conn.commit()
    conn.close()
    logger.info(f'add name: {text} to parcel: {parcel_id}')


def second_track(id):
    conn = sqlite3.connect('parcels.db')
    cursor = conn.cursor()
    cursor.execute(f'select name,date,second_track_number from parcels where user_id="{id}" and second_track_number != "";')
    result = cursor.fetchall()
    if result:
        d = {}
        for i in result:
            parcel_name, date, second_track_number = i
            if second_track_number not in d.keys():
                d[second_track_number] = f'<b>{parcel_name}</b>{time_on_the_road(date)}\n'
            else:
                d[second_track_number] += f'<b>{parcel_name}</b>{time_on_the_road(date)}\n'
        for i in d:
            text = f'<b>{i}</b>\n{d[i]}'
            send('sendMessage', chat_id=id, parse_mode='HTML', text=text)
